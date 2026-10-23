//! Primeiro caminho vertical Slint: projeto -> tarefa -> iniciar -> pausar.
//! I05 adicionara tray/HUD, reconhecimento e ciclo de vida de janelas.
slint::include_modules!();

use anyhow::{anyhow, Result};
#[cfg(windows)]
use std::path::Path;
use std::{cell::RefCell, path::PathBuf, rc::Rc, time::Duration};
use timeros_core::persistence::{json::JsonStore, sqlite::WorkRepository};
use timeros_core::system_clock::SystemClock;

struct App {
    repo: WorkRepository<SystemClock>,
    _json: JsonStore,
    project_id: Option<String>,
    task_id: Option<String>,
}

/// Dados portateis pertencem a pasta do executavel, nao ao CWD do atalho/shell.
fn portable_data_dir() -> Result<PathBuf> {
    let executable = std::env::current_exe()?;
    let dir = executable
        .parent()
        .ok_or_else(|| anyhow!("pasta do executavel indisponivel"))?;
    Ok(dir.join("data"))
}

/// A exclusividade do handle protege a recuperacao SQLite de outra instancia.
/// Nunca apagar o arquivo de lock: ele e reutilizavel apos crash/fechamento.
#[cfg(windows)]
fn acquire_instance_guard(data: &Path) -> Result<std::fs::File> {
    use std::fs::OpenOptions;
    use std::os::windows::fs::OpenOptionsExt;

    std::fs::create_dir_all(data)?;
    OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .share_mode(0)
        .open(data.join(".timeros.lock"))
        .map_err(|e| {
            anyhow!("TimerOS ja esta aberto nesta pasta de dados ou o lock esta indisponivel: {e}")
        })
}

fn main() -> Result<()> {
    let data = portable_data_dir()?;
    // Antes de JsonStore::open e WorkRepository::open (que executa recovery).
    #[cfg(windows)]
    let _instance_guard = acquire_instance_guard(&data)?;

    let json = JsonStore::open(&data)?;
    let repo = WorkRepository::open(data.join("timeros.db"), SystemClock::new())?;
    let project_id = repo.projects()?.first().map(|p| p.id.clone());
    let task_id = match &project_id {
        Some(id) => repo.tasks(id)?.first().map(|t| t.id.clone()),
        None => None,
    };
    let state = Rc::new(RefCell::new(App {
        repo,
        _json: json,
        project_id,
        task_id,
    }));
    let ui = AppWindow::new()?;
    refresh(&ui, &state);

    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_create_project(move |name| {
            let outcome = (|| -> Result<()> {
                let id = state.borrow_mut().repo.create_project(name.as_str())?;
                let mut s = state.borrow_mut();
                s.project_id = Some(id);
                s.task_id = None;
                Ok(())
            })();
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_create_task(move |name| {
            let outcome = (|| -> Result<()> {
                let project_id = state
                    .borrow()
                    .project_id
                    .clone()
                    .ok_or_else(|| anyhow!("crie um projeto primeiro"))?;
                let id = state
                    .borrow_mut()
                    .repo
                    .create_task(&project_id, name.as_str())?;
                state.borrow_mut().task_id = Some(id);
                Ok(())
            })();
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_start_task(move || {
            let outcome = act(&state, "start");
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_pause_task(move || {
            let outcome = act(&state, "pause");
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_resume_task(move || {
            let outcome = act(&state, "resume");
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_select_project(move |index| {
            let outcome = (|| -> Result<()> {
                let projects = state.borrow().repo.projects()?;
                let chosen = projects
                    .get(usize::try_from(index)?)
                    .ok_or_else(|| anyhow!("projeto selecionado invalido"))?
                    .id
                    .clone();
                let task_id = state
                    .borrow()
                    .repo
                    .tasks(&chosen)?
                    .first()
                    .map(|task| task.id.clone());
                let mut s = state.borrow_mut();
                s.project_id = Some(chosen);
                s.task_id = task_id;
                Ok(())
            })();
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_select_task(move |index| {
            let outcome = (|| -> Result<()> {
                let project_id = state
                    .borrow()
                    .project_id
                    .clone()
                    .ok_or_else(|| anyhow!("selecione projeto primeiro"))?;
                let tasks = state.borrow().repo.tasks(&project_id)?;
                let task_id = tasks
                    .get(usize::try_from(index)?)
                    .ok_or_else(|| anyhow!("tarefa selecionada invalida"))?
                    .id
                    .clone();
                state.borrow_mut().task_id = Some(task_id);
                Ok(())
            })();
            show(&weak, &state, outcome);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_refresh(move || {
            if let Some(ui) = weak.upgrade() {
                refresh(&ui, &state);
            }
        });
    }

    // Um checkpoint por minuto enquanto a UI esta viva; nao por repaint.
    let checkpoint_timer = slint::Timer::default();
    {
        let state = state.clone();
        let weak = ui.as_weak();
        checkpoint_timer.start(
            slint::TimerMode::Repeated,
            Duration::from_secs(60),
            move || {
                let result = state.borrow_mut().repo.checkpoint();
                if let Some(ui) = weak.upgrade() {
                    if let Err(e) = result {
                        ui.set_status_line(format!("Falha de checkpoint: {e}").into());
                    }
                    refresh(&ui, &state);
                }
            },
        );
    }

    ui.run()?;
    // O prototipo encerra o processo ao fechar a janela; tray e responsabilidade I05.
    state.borrow_mut().repo.close_safely()?;
    Ok(())
}

fn act(state: &Rc<RefCell<App>>, operation: &str) -> Result<()> {
    let id = state
        .borrow()
        .task_id
        .clone()
        .ok_or_else(|| anyhow!("crie uma tarefa primeiro"))?;
    state.borrow_mut().repo.transition(&id, operation)
}

fn refresh(ui: &AppWindow, state: &Rc<RefCell<App>>) {
    let s = state.borrow();
    match s.repo.projects() {
        Ok(projects) => {
            let selected = projects
                .iter()
                .position(|p| Some(&p.id) == s.project_id.as_ref())
                .and_then(|i| i32::try_from(i).ok())
                .unwrap_or(-1);
            let names: Vec<slint::SharedString> =
                projects.iter().map(|p| p.name.as_str().into()).collect();
            ui.set_project_options(slint::ModelRc::from(Rc::new(slint::VecModel::from(names))));
            ui.set_selected_project_index(selected);
        }
        Err(e) => {
            ui.set_status_line(format!("Erro ao carregar projetos: {e}").into());
        }
    }
    if let Some(id) = &s.project_id {
        match s.repo.project_metrics(id) {
            Ok(m) => ui.set_project_metrics(
                format!(
                    "Projeto: tempo proprio {} min | soma das tarefas {} min | ativas {}",
                    m.own_elapsed_ms / 60_000,
                    m.task_time_ms / 60_000,
                    m.running_task_count
                )
                .into(),
            ),
            Err(e) => ui.set_project_metrics(format!("Erro de leitura: {e}").into()),
        }
        match s.repo.tasks(id) {
            Ok(tasks) => {
                let selected = tasks
                    .iter()
                    .position(|t| Some(&t.id) == s.task_id.as_ref())
                    .and_then(|i| i32::try_from(i).ok())
                    .unwrap_or(-1);
                let names: Vec<slint::SharedString> =
                    tasks.iter().map(|t| t.name.as_str().into()).collect();
                ui.set_task_options(slint::ModelRc::from(Rc::new(slint::VecModel::from(names))));
                ui.set_selected_task_index(selected);
                if let Some(task) = tasks.get(usize::try_from(selected).unwrap_or(usize::MAX)) {
                    ui.set_task_status(format!("Tarefa: {} ({})", task.name, task.status).into());
                } else {
                    ui.set_task_status("Sem tarefa selecionada".into());
                }
            }
            Err(e) => ui.set_status_line(format!("Erro ao carregar tarefas: {e}").into()),
        }
    } else {
        ui.set_project_metrics("Sem projeto selecionado".into());
        ui.set_task_options(slint::ModelRc::from(Rc::new(slint::VecModel::from(Vec::<
            slint::SharedString,
        >::new(
        )))));
        ui.set_selected_task_index(-1);
        ui.set_task_status("Sem tarefa selecionada".into());
    }
}

fn show(weak: &slint::Weak<AppWindow>, state: &Rc<RefCell<App>>, outcome: Result<()>) {
    if let Some(ui) = weak.upgrade() {
        ui.set_status_line(match outcome {
            Ok(()) => "Gravacao confirmada no SQLite".into(),
            Err(e) => format!("Sem confirmacao: {e}").into(),
        });
        refresh(&ui, state);
    }
}

#[cfg(all(test, windows))]
mod tests {
    use super::acquire_instance_guard;

    #[test]
    fn same_portable_data_dir_rejects_second_instance() {
        let root = tempfile::tempdir().unwrap();
        let first = acquire_instance_guard(root.path()).unwrap();
        assert!(acquire_instance_guard(root.path()).is_err());
        drop(first);
        assert!(acquire_instance_guard(root.path()).is_ok());
    }
}
