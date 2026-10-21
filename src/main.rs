//! Primeiro caminho vertical Slint: projeto -> tarefa -> iniciar -> pausar.
//! I05 adicionara tray/HUD, reconhecimento e ciclo de vida de janelas.
slint::include_modules!();
use anyhow::{anyhow, Result};
use std::{cell::RefCell, path::PathBuf, rc::Rc, time::Duration};
use timeros_core::persistence::{json::JsonStore, sqlite::WorkRepository};
use timeros_core::system_clock::SystemClock;

struct App {
    repo: WorkRepository<SystemClock>,
    _json: JsonStore,
    project_id: Option<String>,
    task_id: Option<String>,
}

fn main() -> Result<()> {
    let data=PathBuf::from("data");
    let json=JsonStore::open(&data)?;
    let repo=WorkRepository::open(data.join("timeros.db"),SystemClock::new())?;
    let project_id=repo.projects()?.first().map(|p|p.id.clone());
    let task_id=match &project_id {Some(id)=>repo.tasks(id)?.first().map(|t|t.id.clone()),None=>None};
    let state=Rc::new(RefCell::new(App{repo,_json:json,project_id,task_id}));
    let ui=AppWindow::new()?;
    refresh(&ui,&state);
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_create_project(move |name|{
            let outcome=(||->Result<()> {
                let id=state.borrow_mut().repo.create_project(name.as_str())?;
                let mut s=state.borrow_mut();s.project_id=Some(id);s.task_id=None;Ok(())
            })();show(&weak,&state,outcome);
        });
    }
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_create_task(move |name|{
            let outcome=(||->Result<()> {
                let project_id=state.borrow().project_id.clone().ok_or_else(||anyhow!("crie um projeto primeiro"))?;
                let id=state.borrow_mut().repo.create_task(&project_id,name.as_str())?;
                state.borrow_mut().task_id=Some(id);Ok(())
            })();show(&weak,&state,outcome);
        });
    }
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_start_task(move ||{let outcome=act(&state,"start");show(&weak,&state,outcome);});
    }
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_pause_task(move ||{let outcome=act(&state,"pause");show(&weak,&state,outcome);});
    }
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_resume_task(move ||{let outcome=act(&state,"resume");show(&weak,&state,outcome);});
    }
    {
        let state=state.clone();let weak=ui.as_weak();
        ui.on_refresh(move ||{if let Some(ui)=weak.upgrade(){refresh(&ui,&state);}});
    }
    // Um checkpoint por minuto enquanto a UI esta viva. Nunca uma escrita por repaint.
    let checkpoint_timer=slint::Timer::default();
    {
        let state=state.clone();let weak=ui.as_weak();
        checkpoint_timer.start(slint::TimerMode::Repeated,Duration::from_secs(60),move || {
            let result=state.borrow_mut().repo.checkpoint();
            if let Some(ui)=weak.upgrade(){
                if let Err(e)=result {ui.set_status_line(format!("Falha de checkpoint: {e}").into());}
                refresh(&ui,&state);
            }
        });
    }
    ui.run()?;
    // Fechamento desta janela de prova encerra o processo; tray sera introduzido em I05.
    // Diferente de um crash, o fechamento normal persiste o parcial atual.
    state.borrow_mut().repo.close_safely()?;
    Ok(())
}
fn act(state:&Rc<RefCell<App>>,operation:&str)->Result<()> {
    let id=state.borrow().task_id.clone().ok_or_else(||anyhow!("crie uma tarefa primeiro"))?;
    state.borrow_mut().repo.transition(&id,operation)
}
fn refresh(ui:&AppWindow,state:&Rc<RefCell<App>>) {
    let s=state.borrow();
    if let Some(id)=&s.project_id {
        match s.repo.project_metrics(id) {
            Ok(m)=>ui.set_project_metrics(format!("Projeto: tempo proprio {} min | soma das tarefas {} min | ativas {}",m.own_elapsed_ms/60000,m.task_time_ms/60000,m.running_task_count).into()),
            Err(e)=>ui.set_project_metrics(format!("Erro de leitura: {e}").into()),
        }
        if let Ok(tasks)=s.repo.tasks(id){
            if let Some(selected)=tasks.iter().find(|t|Some(&t.id)==s.task_id.as_ref()) {
                ui.set_task_status(format!("Tarefa: {} ({})",selected.name,selected.status).into());
            }
        }
    }
}
fn show(weak:&slint::Weak<AppWindow>,state:&Rc<RefCell<App>>,outcome:Result<()>) {
    if let Some(ui)=weak.upgrade(){
        ui.set_status_line(match outcome {Ok(())=>"Gravacao confirmada no SQLite".into(),Err(e)=>format!("Sem confirmacao: {e}").into()});
        refresh(&ui,state);
    }
}