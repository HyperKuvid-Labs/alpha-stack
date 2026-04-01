use rust_mcts_engine::mcts::{Mcts, MctsState};

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct DummyState {
    depth: usize,
    max_depth: usize,
    path: Vec<i32>,
}

impl MctsState for DummyState {
    type Move = i32;

    fn get_legal_moves(&self) -> Vec<Self::Move> {
        if self.depth >= self.max_depth {
            vec![]
        } else {
            vec![0, 1] 
        }
    }

    fn apply_move(&self, m: &Self::Move) -> Self {
        let mut new_path = self.path.clone();
        new_path.push(*m);
        DummyState {
            depth: self.depth + 1,
            max_depth: self.max_depth,
            path: new_path,
        }
    }

    fn is_terminal(&self) -> bool {
        self.depth >= self.max_depth
    }

    fn get_reward(&self) -> f64 {
        // Path 1 is good (reward 1.0), Path 0 is bad (reward 0.0)
        if self.path.len() > 0 && self.path[0] == 1 {
            1.0
        } else {
            0.0
        }
    }
}

#[test]
fn test_mcts_convergence_on_simple_tree() {
    let initial_state = DummyState { depth: 0, max_depth: 3, path: vec![] };
    let mut mcts = Mcts::new(initial_state);

    mcts.run(500);

    let best_move = mcts.get_best_move();
    assert_eq!(best_move, Some(1));
}

#[test]
fn test_mcts_terminal_state() {
    let initial_state = DummyState { depth: 3, max_depth: 3, path: vec![1, 1, 1] };
    let mut mcts = Mcts::new(initial_state);
    
    mcts.run(10);
    assert!(mcts.get_best_move().is_none());
}
