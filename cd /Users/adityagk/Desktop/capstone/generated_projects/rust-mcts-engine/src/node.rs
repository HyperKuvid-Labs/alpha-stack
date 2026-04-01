use std::sync::{Arc, Mutex, Weak};

pub struct MCTSNode<Action, State> {
    pub state: State,
    pub parent: Option<Weak<Mutex<MCTSNode<Action, State>>>>,
    pub children: Vec<Arc<Mutex<MCTSNode<Action, State>>>>,
    pub action: Option<Action>,
    pub visit_count: u64,
    pub value_sum: f64,
}

impl<Action, State> MCTSNode<Action, State> {
    pub fn new(state: State, action: Option<Action>, parent: Option<Weak<Mutex<MCTSNode<Action, State>>>>) -> Self {
        Self {
            state,
            parent,
            children: Vec::new(),
            action,
            visit_count: 0,
            value_sum: 0.0,
        }
    }

    pub fn is_fully_expanded(&self, legal_actions_count: usize) -> bool {
        self.children.len() == legal_actions_count
    }

    pub fn update(&mut self, reward: f64) {
        self.visit_count += 1;
        self.value_sum += reward;
    }

    pub fn average_value(&self) -> f64 {
        if self.visit_count == 0 {
            0.0
        } else {
            self.value_sum / self.visit_count as f64
        }
    }
}
