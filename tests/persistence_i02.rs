use timeros_core::clock::FakeClock;
use timeros_core::persistence::json::{ConfigSnapshot,JsonStore};
use timeros_core::persistence::sqlite::WorkRepository;
use tempfile::tempdir;
const MIN:u64=60_000;
fn fixture()->(tempfile::TempDir,FakeClock){(tempdir().unwrap(),FakeClock::new(1_790_000_000_000,0))}

#[test]
fn migration_and_foreign_keys() {
    let (dir,clock)=fixture();let path=dir.path().join("timeros.db");
    let mut repo=WorkRepository::open(&path,clock).unwrap();
    assert!(repo.create_task("does-not-exist","Orphan").is_err());
    let project=repo.create_project("P").unwrap();
    assert!(repo.create_task(&project,"T").is_ok());
    drop(repo);
    let db=rusqlite::Connection::open(path).unwrap();
    let v:i64=db.pragma_query_value(None,"user_version",|r|r.get(0)).unwrap();
    assert_eq!(v,1);
}
#[test]
fn overlap_60_120_and_checkpoint_idempotent() {
    let (dir,clock)=fixture();let mut repo=WorkRepository::open(dir.path().join("db"),clock.clone()).unwrap();
    let p=repo.create_project("P").unwrap();let a=repo.create_task(&p,"A").unwrap();let b=repo.create_task(&p,"B").unwrap();
    repo.transition(&a,"start").unwrap();repo.transition(&b,"start").unwrap();
    clock.advance_both_ms(MIN*60);repo.checkpoint().unwrap();repo.checkpoint().unwrap();
    let m=repo.project_metrics(&p).unwrap();
    assert_eq!((m.own_elapsed_ms,m.task_time_ms,m.running_task_count),(MIN*60,MIN*120,2));
    repo.transition(&a,"pause").unwrap();clock.advance_both_ms(MIN*30);
    let m=repo.project_metrics(&p).unwrap();assert_eq!((m.own_elapsed_ms,m.task_time_ms),(MIN*90,MIN*150));
}
#[test]
fn rollback_not_acknowledged() {
    let (dir,clock)=fixture();let mut repo=WorkRepository::open(dir.path().join("db"),clock).unwrap();
    let p=repo.create_project("P").unwrap();let t=repo.create_task(&p,"T").unwrap();
    repo.fail_once_before_commit();assert!(repo.transition(&t,"start").is_err());
    assert_eq!(repo.tasks(&p).unwrap()[0].status,"stopped");
    assert_eq!(repo.project_metrics(&p).unwrap().running_task_count,0);
}
#[test]
fn crash_restarts_paused_without_unconfirmed_time() {
    let (dir,clock)=fixture();let path=dir.path().join("db");
    let mut repo=WorkRepository::open(&path,clock.clone()).unwrap();
    let p=repo.create_project("P").unwrap();let t=repo.create_task(&p,"T").unwrap();
    repo.transition(&t,"start").unwrap();clock.advance_both_ms(MIN*5);repo.checkpoint().unwrap();
    clock.advance_both_ms(MIN*12);drop(repo);
    let repo=WorkRepository::open(&path,clock).unwrap();
    assert_eq!(repo.tasks(&p).unwrap()[0].status,"paused");
    let m=repo.project_metrics(&p).unwrap();assert_eq!((m.own_elapsed_ms,m.task_time_ms),(MIN*5,MIN*5));
}
#[test]
fn pause_resume_two_sessions() {
    let (dir,clock)=fixture();let path=dir.path().join("db");
    let mut repo=WorkRepository::open(&path,clock.clone()).unwrap();
    let p=repo.create_project("P").unwrap();let t=repo.create_task(&p,"T").unwrap();
    repo.transition(&t,"start").unwrap();clock.advance_both_ms(MIN);repo.transition(&t,"pause").unwrap();
    clock.advance_both_ms(MIN*50);repo.transition(&t,"resume").unwrap();clock.advance_both_ms(MIN*2);
    repo.close_safely().unwrap();drop(repo);
    let repo=WorkRepository::open(&path,clock).unwrap();
    assert_eq!(repo.tasks(&p).unwrap()[0].status,"paused");
    assert_eq!(repo.project_metrics(&p).unwrap().task_time_ms,MIN*3);
    let db=rusqlite::Connection::open(path).unwrap();
    let cnt:i64=db.query_row("SELECT count(*) FROM time_entries",[],|r|r.get(0)).unwrap();assert_eq!(cnt,2);
}
#[test]
fn json_roundtrip_revision_backup_and_failure() {
    let (dir,_)=fixture();let mut store=JsonStore::open(dir.path()).unwrap();
    assert_eq!(store.state.revision,0);
    let old=std::fs::read(dir.path().join("state.json")).unwrap();
    store.fail_once_before_replace();
    assert!(store.commit_state(0,store.state.clone(),"2026-10-21T01:00:00Z").is_err());
    assert_eq!(store.state.revision,0);
    assert_eq!(std::fs::read(dir.path().join("state.json")).unwrap(),old);
    store.commit_state(0,store.state.clone(),"2026-10-21T01:00:00Z").unwrap();
    assert_eq!(store.state.revision,1);
    assert_eq!(std::fs::read(dir.path().join("state.json.bak")).unwrap(),old);
    assert_eq!(JsonStore::open(dir.path()).unwrap().state.revision,1);
}
#[test]
fn malformed_json_is_preserved() {
    let (dir,_)=fixture();drop(JsonStore::open(dir.path()).unwrap());
    let bad=b"{ certainly not JSON";
    std::fs::write(dir.path().join("config.json"),bad).unwrap();
    assert!(JsonStore::open(dir.path()).is_err());
    assert_eq!(std::fs::read(dir.path().join("config.json")).unwrap(),bad);
}
#[test]
fn stale_revision_and_unknown_envelope_rejected() {
    let (dir,_)=fixture();let mut store=JsonStore::open(dir.path()).unwrap();
    assert!(store.commit_config(9,ConfigSnapshot::default(),"2026-10-21T01:00:00Z").is_err());
    let wrong = ConfigSnapshot { schema_version: 2, ..ConfigSnapshot::default() };
    assert!(store.commit_config(0,wrong,"2026-10-21T01:00:00Z").is_err());
    drop(store);
    std::fs::write(dir.path().join("config.json"),r#"{"schema_version":99}"#).unwrap();
    assert!(JsonStore::open(dir.path()).is_err());
}

#[test]
fn explicit_restore_preserves_forensic_bytes() {
    let (dir,_)=fixture();let mut store=JsonStore::open(dir.path()).unwrap();
    store.commit_config(0,store.config.clone(),"2026-10-21T01:00:00Z").unwrap();
    drop(store);
    let bad=b"{BROKEN";
    std::fs::write(dir.path().join("config.json"),bad).unwrap();
    assert!(timeros_core::persistence::json::restore_backup_explicit(dir.path(),"config",false).is_err());
    let copy=timeros_core::persistence::json::restore_backup_explicit(dir.path(),"config",true).unwrap();
    assert_eq!(std::fs::read(copy).unwrap(),bad);
    assert!(JsonStore::open(dir.path()).is_ok());
}