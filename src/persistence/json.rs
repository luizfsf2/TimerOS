//! Configuracao e runtime de timers usam documentos diferentes, ambos atomicos.
//! I02 valida envelopes e invariantes transversais; sem executar motores I03/I04.
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConfigSnapshot {
    pub schema_version: u32,
    pub revision: u64,
    pub written_at_utc: String,
    pub preferences: Value,
    pub snooze_presets_ms: Vec<u64>,
    pub countdown_definitions: Vec<Value>,
    pub fixed_alarm_definitions: Vec<Value>,
    pub sequence_definitions: Vec<Value>,
    pub alert_profiles: Vec<Value>,
    pub sounds: Vec<Value>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StateSnapshot {
    pub schema_version: u32,
    pub revision: u64,
    pub written_at_utc: String,
    pub countdown_runs: Vec<Value>,
    pub sequence_runs: Vec<Value>,
    pub alarm_occurrences: Vec<Value>,
    pub fixed_alarm_cursors: Vec<Value>,
}
impl Default for ConfigSnapshot {
    fn default() -> Self {
        Self { schema_version:1,revision:0,written_at_utc:"1970-01-01T00:00:00Z".into(),
            preferences:serde_json::json!({"startup_with_windows":false,"hud":{"always_on_top":true,"visible_timer_ids":[]}}),
            snooze_presets_ms:vec![300_000,600_000],countdown_definitions:vec![],fixed_alarm_definitions:vec![],
            sequence_definitions:vec![],alert_profiles:vec![],sounds:vec![] }
    }
}
impl Default for StateSnapshot {
    fn default() -> Self {
        Self {schema_version:1,revision:0,written_at_utc:"1970-01-01T00:00:00Z".into(),
            countdown_runs:vec![],sequence_runs:vec![],alarm_occurrences:vec![],fixed_alarm_cursors:vec![] }
    }
}
fn unique(values:&[Value],key:&str,category:&str)->Result<HashSet<String>> {
    let mut ids=HashSet::new();
    for item in values {
        let id=item.get(key).and_then(Value::as_str).filter(|s|!s.trim().is_empty())
            .ok_or_else(||anyhow!("{category}.{key} obrigatorio"))?;
        if !ids.insert(id.to_string()) {bail!("{category}: id duplicado {id}");}
    }
    Ok(ids)
}
fn validate_version(version:u32)->Result<()> {
    if version!=1 {bail!("versao JSON nao suportada: {version}");}Ok(())
}
fn validate_timestamp(timestamp:&str)->Result<()> {
    let parsed=chrono::DateTime::parse_from_rfc3339(timestamp)?;
    if parsed.offset().local_minus_utc()!=0 {bail!("written_at_utc deve ser UTC");}
    Ok(())
}
impl ConfigSnapshot {
    pub fn validate(&self)->Result<()> {
        validate_version(self.schema_version)?;validate_timestamp(&self.written_at_utc)?;
        if !self.preferences.is_object() {bail!("preferences deve ser objeto");}
        if self.snooze_presets_ms.iter().any(|v|*v==0||*v%60_000!=0) {bail!("presets devem ser minutos positivos");}
        let profiles=unique(&self.alert_profiles,"id","alert_profiles")?;
        let sounds=unique(&self.sounds,"id","sounds")?;
        for s in &self.sounds {
            let path=s.get("asset_path").and_then(Value::as_str).ok_or_else(||anyhow!("asset_path invalido"))?;
            let p=Path::new(path);
            if p.is_absolute()||p.components().any(|c|matches!(c,std::path::Component::ParentDir|std::path::Component::Prefix(_))) {bail!("som deve apontar para asset relativo seguro");}
        }
        for p in &self.alert_profiles {
            let phases=p.get("phases").and_then(Value::as_array).ok_or_else(||anyhow!("alert profile phases ausentes"))?;
            // I03 definira o avaliador completo. I02 preserva invariantes basicos.
            if phases.is_empty(){bail!("perfil sem fase 0");}
            let mut prior:Option<u64>=None;
            for phase in phases {
                let start=phase.get("starts_after_ms").and_then(Value::as_u64).ok_or_else(||anyhow!("marco de fase invalido"))?;
                if let Some(prev)=prior {if start<=prev {bail!("fases fora de ordem");}}
                else if start!=0 {bail!("primeiro marco apos vencimento deve ser zero");}
                prior=Some(start);
                let actions=phase.get("actions").and_then(Value::as_array).ok_or_else(||anyhow!("actions invalidas"))?;
                for action in actions {
                    if action.get("kind").and_then(Value::as_str)==Some("sound") {
                        let sid=action.get("sound_id").and_then(Value::as_str).ok_or_else(||anyhow!("sound_id ausente"))?;
                        if !sounds.contains(sid){bail!("sound_id inexistente");}
                    }
                }
            }
        }
        for (name,values) in [("countdown_definitions",&self.countdown_definitions),
                              ("fixed_alarm_definitions",&self.fixed_alarm_definitions),
                              ("sequence_definitions",&self.sequence_definitions)] {
            unique(values,"id",name)?;
            for v in values {
                if let Some(profile)=v.get("alert_profile_id").and_then(Value::as_str) {
                    if !profiles.contains(profile){bail!("referencia de perfil desconhecida: {profile}");}
                }
                let label=v.get("name").and_then(Value::as_str).unwrap_or("");
                if label.trim().is_empty() {bail!("{name}: nome obrigatorio");}
            }
        }
        for v in &self.countdown_definitions {
            if v.get("original_duration_ms").and_then(Value::as_u64).unwrap_or(0)==0 {bail!("countdown exige duracao positiva");}
            if !matches!(v.get("mode").and_then(Value::as_str),Some("cyclic"|"one_shot")){bail!("modo countdown invalido");}
        }
        Ok(())
    }
}
impl StateSnapshot {
    pub fn validate(&self)->Result<()> {
        validate_version(self.schema_version)?;validate_timestamp(&self.written_at_utc)?;
        unique(&self.countdown_runs,"run_id","countdown_runs")?;
        unique(&self.sequence_runs,"run_id","sequence_runs")?;
        unique(&self.alarm_occurrences,"occurrence_id","alarm_occurrences")?;
        unique(&self.alarm_occurrences,"slot_key","alarm_occurrences")?;
        unique(&self.fixed_alarm_cursors,"alarm_id","fixed_alarm_cursors")?;
        for run in &self.countdown_runs {
            let status=run.get("status").and_then(Value::as_str).ok_or_else(||anyhow!("status invalido"))?;
            if !matches!(status,"stopped"|"running"|"paused"|"pending") {bail!("status countdown desconhecido");}
            if status=="running"||status=="pending" {
                if run.get("due_at_utc").and_then(Value::as_str).is_none(){bail!("due_at obrigatorio");}
            }
            if status=="paused"&&run.get("paused_remaining_ms").and_then(Value::as_u64).is_none(){bail!("paused sem restante");}
            if run.get("definition_snapshot").is_none(){bail!("run sem snapshot");}
        }
        for run in &self.sequence_runs {
            if run.get("definition_snapshot").is_none(){bail!("sequence run sem snapshot");}
        }
        for occ in &self.alarm_occurrences {
            for key in ["alarm_id","scheduled_for_utc","effective_due_at_utc"] {
                if occ.get(key).and_then(Value::as_str).is_none(){bail!("ocorrencia sem {key}");}
            }
            if !matches!(occ.get("status").and_then(Value::as_str),Some("pending"|"snoozed")) {bail!("status ocorrencia invalido");}
        }
        Ok(())
    }
}
pub struct JsonStore { pub config:ConfigSnapshot, pub state:StateSnapshot, data_dir:PathBuf, fail_next_replace:bool }
impl JsonStore {
    pub fn open(data_dir:impl Into<PathBuf>)->Result<Self> {
        let data_dir=data_dir.into(); fs::create_dir_all(&data_dir)?;
        let config_path=data_dir.join("config.json");let state_path=data_dir.join("state.json");
        let config_exists=config_path.exists();let state_exists=state_path.exists();
        if !config_exists && !state_exists && !data_dir.join("config.json.bak").exists() && !data_dir.join("state.json.bak").exists() {
            let store=Self{config:ConfigSnapshot::default(),state:StateSnapshot::default(),data_dir,fail_next_replace:false};
            store.config.validate()?;store.state.validate()?;
            // Defaults somente quando nao havia dados em nenhum dos dois proprietarios.
            write_atomically(&config_path,&serde_json::to_vec_pretty(&store.config)?)?;
            write_atomically(&state_path,&serde_json::to_vec_pretty(&store.state)?)?;
            return Ok(store);
        }
        if !config_exists||!state_exists { bail!("JSON ausente em instalacao existente; nao criar defaults silenciosamente"); }
        let config:ConfigSnapshot=serde_json::from_slice(&fs::read(&config_path).context("ler config.json")?)
            .context("config.json corrompido: preservar arquivo e corrigir explicitamente")?;
        let state:StateSnapshot=serde_json::from_slice(&fs::read(&state_path).context("ler state.json")?)
            .context("state.json corrompido: preservar arquivo e corrigir explicitamente")?;
        config.validate()?;state.validate()?;
        Ok(Self{config,state,data_dir,fail_next_replace:false})
    }
    pub fn fail_once_before_replace(&mut self){self.fail_next_replace=true;}
    pub fn commit_config(&mut self, expected:u64, mut next:ConfigSnapshot, utc_timestamp:&str)->Result<()> {
        if expected!=self.config.revision {bail!("conflito de revisao de config");}
        next.revision=expected.checked_add(1).ok_or_else(||anyhow!("overflow revision"))?;
        next.written_at_utc=utc_timestamp.into();next.validate()?;
        let path=self.data_dir.join("config.json");
        let fail=std::mem::take(&mut self.fail_next_replace);
        replace_with_backup(&path,&serde_json::to_vec_pretty(&next)?,fail)?;
        self.config=next;Ok(())
    }
    pub fn commit_state(&mut self, expected:u64, mut next:StateSnapshot, utc_timestamp:&str)->Result<()> {
        if expected!=self.state.revision {bail!("conflito de revisao de state");}
        next.revision=expected.checked_add(1).ok_or_else(||anyhow!("overflow revision"))?;
        next.written_at_utc=utc_timestamp.into();next.validate()?;
        let path=self.data_dir.join("state.json");
        let fail=std::mem::take(&mut self.fail_next_replace);
        replace_with_backup(&path,&serde_json::to_vec_pretty(&next)?,fail)?;
        self.state=next;Ok(())
    }
}

/// Restauracao SOMENTE apos escolha explicita; nunca efetuada durante boot.
/// Guarda os bytes suspeitos em arquivo forense antes da substituicao.
pub fn restore_backup_explicit(data_dir:&Path, owner:&str, confirmed:bool)->Result<PathBuf> {
    if !confirmed {bail!("restauracao exige confirmacao explicita");}
    let (file,valid)=match owner {
        "config"=>("config.json",true),
        "state"=>("state.json",false),
        _=>bail!("proprietario desconhecido"),
    };
    let path=data_dir.join(file);
    let backup=data_dir.join(format!("{file}.bak"));
    let backup_bytes=fs::read(&backup).context("backup inexistente ou ilegivel")?;
    if valid {
        let value:ConfigSnapshot=serde_json::from_slice(&backup_bytes)?;value.validate()?;
    } else {
        let value:StateSnapshot=serde_json::from_slice(&backup_bytes)?;value.validate()?;
    }
    let suspect=fs::read(&path).context("arquivo suspeito ausente; nao sobrescrever")?;
    let forensic=data_dir.join(format!("{file}.corrupt.{}",Uuid::new_v4()));
    write_synced(&forensic,&suspect)?;
    // Substituicao atomica no mesmo volume sem promover suspeito ao backup.
    write_atomically(&path,&backup_bytes)?;
    Ok(forensic)
}

fn write_synced(path:&Path, bytes:&[u8])->Result<()> {
    let mut file=OpenOptions::new().write(true).create_new(true).open(path)?;
    file.write_all(bytes)?;file.flush()?;file.sync_all()?;Ok(())
}
fn replace_file(source:&Path,target:&Path)->Result<()> {
    #[cfg(windows)] {
        use std::os::windows::ffi::OsStrExt;
        let from:Vec<u16>=source.as_os_str().encode_wide().chain(Some(0)).collect();
        let to:Vec<u16>=target.as_os_str().encode_wide().chain(Some(0)).collect();
        // MoveFileExW: REPLACE_EXISTING | WRITE_THROUGH. Mesmo volume.
        #[link(name="kernel32")]
        unsafe extern "system" { fn MoveFileExW(existing:*const u16,new:*const u16,flags:u32)->i32; }
        let success=unsafe{MoveFileExW(from.as_ptr(),to.as_ptr(),0x1|0x8)};
        if success==0 {return Err(std::io::Error::last_os_error().into());}
    }
    #[cfg(not(windows))] {fs::rename(source,target)?;}
    Ok(())
}
fn write_atomically(path:&Path,bytes:&[u8])->Result<()> {
    let temp=path.with_extension(format!("{}.tmp",Uuid::new_v4()));
    write_synced(&temp,bytes)?;
    if let Err(e)=replace_file(&temp,path) {let _=fs::remove_file(&temp);return Err(e);}
    #[cfg(unix)] { if let Some(dir)=path.parent() { fs::File::open(dir)?.sync_all()?; } }
    Ok(())
}
fn replace_with_backup(path:&Path,bytes:&[u8],fail:bool)->Result<()> {
    // Caller validou o documento oficial em open. Conferir novamente antes de backup.
    let old=fs::read(path).context("JSON oficial ausente; preservar e diagnosticar")?;
    let old_value:Value=serde_json::from_slice(&old).context("JSON oficial invalido; nao substituir")?;
    let schema=old_value.get("schema_version").and_then(Value::as_u64).ok_or_else(||anyhow!("schema_version ausente"))?;
    if schema!=1 {bail!("schema nao suportado, preservar oficial");}
    if path.file_name().and_then(|s|s.to_str())==Some("config.json") {
        let old_doc:ConfigSnapshot=serde_json::from_slice(&old)?;old_doc.validate()?;
    } else {
        let old_doc:StateSnapshot=serde_json::from_slice(&old)?;old_doc.validate()?;
    }
    let backup=PathBuf::from(format!("{}.bak",path.display()));
    write_atomically(&backup,&old)?;
    if fail {bail!("falha injetada antes de substituir JSON oficial");}
    write_atomically(path,bytes)
}