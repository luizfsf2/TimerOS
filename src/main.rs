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
    // Navegação explícita: nenhuma selecao emula escrita no modelo da UI.
    // Isso evita reentrancia e realimentacao dos ComboBoxes dinamicos.
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_previous_project(move || {
            let result = select_project(&state, true);
            show_selection(&weak, &state, result);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_next_project(move || {
            let result = select_project(&state, false);
            show_selection(&weak, &state, result);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_previous_task(move || {
            let result = select_task(&state, true);
            show_selection(&weak, &state, result);
        });
    }
    {
        let state = state.clone();
        let weak = ui.as_weak();
        ui.on_next_task(move || {
            let result = select_task(&state, false);
            show_selection(&weak, &state, result);
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

/// Seleciona uma entrada adjacente, com retorno circular e fallback previsivel.
fn adjacent_index(len: usize, current: Option<usize>, backwards: bool) -> Option<usize> {
    if len == 0 {
        return None;
    }
    match current {
        Some(index) if index < len => {
            Some(if backwards { (index + len - 1) % len } else { (index + 1) % len })
        }
        _ => Some(if backwards { len - 1 } else { 0 }),
    }
}

fn select_project(state: &Rc<RefCell<App>>, backwards: bool) -> Result<()> {
    let (project_id, task_id) = {
        let current = state.borrow();
        let projects = current.repo.projects()?;
        let position = projects.iter().position(|p| Some(&p.id) == current.project_id.as_ref());
        let index = adjacent_index(projects.len(), position, backwards)
            .ok_or_else(|| anyhow!("crie um projeto primeiro"))?;
        let project_id = projects[index].id.clone();
        let task_id = current.repo.tasks(&project_id)?.first().map(|t| t.id.clone());
        (project_id, task_id)
    };
    let mut current = state.borrow_mut();
    current.project_id = Some(project_id);
    current.task_id = task_id;
    Ok(())
}

fn select_task(state: &Rc<RefCell<App>>, backwards: bool) -> Result<()> {
    let task_id = {
        let current = state.borrow();
        let project_id = current.project_id.as_ref()
            .ok_or_else(|| anyhow!("selecione um projeto primeiro"))?;
        let tasks = current.repo.tasks(project_id)?;
        let position = tasks.iter().position(|t| Some(&t.id) == current.task_id.as_ref());
        let index = adjacent_index(tasks.len(), position, backwards)
            .ok_or_else(|| anyhow!("crie uma tarefa primeiro"))?;
        tasks[index].id.clone()
    };
    state.borrow_mut().task_id = Some(task_id);
    Ok(())
}

fn refresh(ui: &AppWindow, state: &Rc<RefCell<App>>) {
    // Leitura apenas: nao recriar modelos/indices ligados aos controles da UI.
    let current = state.borrow();
    match current.repo.projects() {
        Ok(projects) => {
            let selected = projects.iter().position(|p| Some(&p.id) == current.project_id.as_ref());
            let label = selected
                .map(|index| format!("Projeto {}/{}: {}", index + 1, projects.len(), projects[index].name))
                .unwrap_or_else(|| "Nenhum projeto selecionado".to_string());
            ui.set_selected_project_label(label.into());
        }
        Err(e) => ui.set_status_line(format!("Erro ao carregar projetos: {e}").into()),
    }
    if let Some(project_id) = &current.project_id {
        match current.repo.project_metrics(project_id) {
            Ok(m) => ui.set_project_metrics(format!(
                "Tempo próprio: {} min | soma das tarefas: {} min | ativas: {}",
                m.own_elapsed_ms / 60_000, m.task_time_ms / 60_000, m.running_task_count
            ).into()),
            Err(e) => ui.set_project_metrics(format!("Erro ao ler métricas: {e}").into()),
        }
        match current.repo.tasks(project_id) {
            Ok(tasks) => {
                let selected = tasks.iter().position(|t| Some(&t.id) == current.task_id.as_ref());
                let label = selected
                    .map(|index| format!("Tarefa {}/{}: {}", index + 1, tasks.len(), tasks[index].name))
                    .unwrap_or_else(|| "Nenhuma tarefa selecionada".to_string());
                ui.set_selected_task_label(label.into());
                let status = selected
                    .map(|index| format!("Estado: {}", tasks[index].status))
                    .unwrap_or_else(|| "Sem tarefa selecionada".to_string());
                ui.set_task_status(status.into());
            }
            Err(e) => ui.set_status_line(format!("Erro ao carregar tarefas: {e}").into()),
        }
    } else {
        ui.set_project_metrics("Sem projeto selecionado".into());
        ui.set_selected_task_label("Nenhuma tarefa selecionada".into());
        ui.set_task_status("Sem tarefa selecionada".into());
    }
}

fn show_selection(weak: &slint::Weak<AppWindow>, state: &Rc<RefCell<App>>, outcome: Result<()>) {
    if let Some(ui) = weak.upgrade() {
        ui.set_status_line(match outcome {
            Ok(()) => "Seleção alterada".into(),
            Err(e) => format!("Seleção não alterada: {e}").into(),
        });
        refresh(&ui, state);
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
    use super::{acquire_instance_guard, adjacent_index};

    #[test]
    fn navigation_is_circular_and_has_no_side_effects() {
        assert_eq!(adjacent_index(0, None, false), None);
        assert_eq!(adjacent_index(2, Some(0), true), Some(1));
        assert_eq!(adjacent_index(2, Some(1), false), Some(0));
        assert_eq!(adjacent_index(2, None, false), Some(0));
        assert_eq!(adjacent_index(2, None, true), Some(1));
        assert_eq!(adjacent_index(2, Some(99), false), Some(0));
    }

    #[test]
    fn same_portable_data_dir_rejects_second_instance() {
        let root = tempfile::tempdir().unwrap();
        let first = acquire_instance_guard(root.path()).unwrap();
        assert!(acquire_instance_guard(root.path()).is_err());
        drop(first);
        assert!(acquire_instance_guard(root.path()).is_ok());
    }
}
