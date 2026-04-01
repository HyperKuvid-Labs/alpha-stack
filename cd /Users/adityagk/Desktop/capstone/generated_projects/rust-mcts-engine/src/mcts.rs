use std::collections::HashMap;
use std::hash::Hash;
use rand::seq::SliceRandom;
use rand::thread_rng;

pub trait MctsState: Clone {
    type Move: Clone + Eq + Hash;

    fn get_legal_moves(&self) -> Vec<Self::Move>;
    fn apply_move(&self, m: &Self::Move) -> Self;
    fn is_terminal(&self) -> bool;
    fn get_reward(&self) -> f64;
}

pub struct Node<S: MctsState> {
    pub state: S,
    pub parent: Option<*mut Node<S>>,
    pub children: HashMap<S::Move, Node<S>>,
    pub untried_moves: Vec<S::Move>,
    pub visits: usize,
    pub score: f64,
}

impl<S: MctsState> Node<S> {
    pub fn new(state: S, parent: Option<*mut Node<S>>) -> Self {
        let untried_moves = state.get_legal_moves();
        Node {
            state,
            parent,
            children: HashMap::new(),
            untried_moves,
            visits: 0,
            score: 0.0,
        }
    }

    pub fn is_fully_expanded(&self) -> bool {
        self.untried_moves.is_empty()
    }
}

pub struct Mcts<S: MctsState> {
    pub root: Node<S>,
}

impl<S: MctsState> Mcts<S> {
    pub fn new(initial_state: S) -> Self {
        Mcts {
            root: Node::new(initial_state, None),
        }
    }

    pub fn get_best_move(&self) -> Option<S::Move> {
        let mut best_m = None;
        let mut best_visits = 0;

        for (m, child) in &self.root.children {
            if child.visits > best_visits {
                best_visits = child.visits;
                best_m = Some(m.clone());
            }
        }
        best_m
    }

    pub fn run(&mut self, iterations: usize) {
        for _ in 0..iterations {
            let mut curr_node_ptr: *mut Node<S> = &mut self.root;
            
            unsafe {
                while (*curr_node_ptr).is_fully_expanded() && !(*curr_node_ptr).state.is_terminal() {
                    curr_node_ptr = self.select_best_child_ptr(curr_node_ptr);
                }

                if !(*curr_node_ptr).state.is_terminal() && !(*curr_node_ptr).untried_moves.is_empty() {
                    let m = (*curr_node_ptr).untried_moves.pop().unwrap();
                    let new_state = (*curr_node_ptr).state.apply_move(&m);
                    let child = Node::new(new_state, Some(curr_node_ptr));
                    (*curr_node_ptr).children.insert(m.clone(), child);
                    curr_node_ptr = (*curr_node_ptr).children.get_mut(&m).map_or(std::ptr::null_mut(), |n| n as *mut Node<S>);
                }

                let reward = self.simulate(&(*curr_node_ptr).state);
                self.backpropagate(curr_node_ptr, reward);
            }
        }
    }

    fn select_best_child_ptr(&self, node_ptr: *mut Node<S>) -> *mut Node<S> {
        unsafe {
            let node = &*node_ptr;
            let mut best_m = None;
            let mut best_score = f64::NEG_INFINITY;
            let parent_visits = node.visits as f64;

            for (m, child) in &node.children {
                let uct_score = (child.score / child.visits as f64) + 
                                1.414 * (parent_visits.ln() / child.visits as f64).sqrt();
                if uct_score > best_score {
                    best_score = uct_score;
                    best_m = Some(m.clone());
                }
            }
            node.children.get(&best_m.unwrap()).unwrap() as *const Node<S> as *mut Node<S>
        }
    }

    fn simulate(&self, state: &S) -> f64 {
        let mut curr = state.clone();
        let mut rng = thread_rng();
        while !curr.is_terminal() {
            let moves = curr.get_legal_moves();
            if let Some(m) = moves.choose(&mut rng) {
                curr = curr.apply_move(m);
            } else {
                break;
            }
        }
        curr.get_reward()
    }

    fn backpropagate(&self, node: *mut Node<S>, reward: f64) {
        unsafe {
            let mut curr = node;
            while !curr.is_null() {
                (*curr).visits += 1;
                (*curr).score += reward;
                curr = (*curr).parent.unwrap_or(std::ptr::null_mut());
            }
        }
    }
}
