use std::{
    sync::Arc,
    time::{Duration, Instant},
};

use rand::Rng;
use stats::SolveStats;

use crate::{common::VRPSolution, dbg_println, vrp_instance::VRPInstance};

#[allow(dead_code)]
pub enum TermCond {
    MaxIters(usize),
    TimeElapsed(Duration),
}

pub struct SolveParams {
    pub terminate: TermCond,
    pub frac_dropped: f64,
    /// jump after this many stagnant iterations
    pub patience: usize,
    // should be set of constructors to use one after the other...
    pub constructor: fn(&Arc<VRPInstance>) -> VRPSolution,
    // could also be a set of jumpers to use randomly between them
    pub jumper: fn(&Arc<VRPInstance>, VRPSolution, f64) -> VRPSolution,
}

// trait for a large neighborhood search (LNS) solver
pub trait LNSSolver {
    type DestroyResult;

    fn new(instance: Arc<VRPInstance>, initial_solution: VRPSolution) -> Self;

    fn current(&self) -> &VRPSolution;

    /// Partially destroy the solution.
    fn destroy(&mut self) -> Self::DestroyResult;

    /// Repair the solution and return the result.
    fn repair(&mut self, res: Self::DestroyResult) -> Result<(), String>;

    fn get_stats_mut(&mut self) -> &mut SolveStats;

    fn jump_to_solution(&mut self, sol: &VRPSolution);

    // Optionally update the tabu for the solver.
    fn update_tabu(&mut self, _res: &Self::DestroyResult) {}
}

pub trait IterativeSolver {
    fn new(instance: Arc<VRPInstance>, initial_solution: VRPSolution) -> Self;

    fn current(&self) -> &VRPSolution;

    fn find_new_solution(&mut self) -> Option<()>;

    fn jump_to_solution(&mut self, sol: &VRPSolution);

    fn get_stats_mut(&mut self) -> &mut SolveStats;

    fn cost(&self) -> f64;
}

pub mod stats {
    use std::collections::HashMap;

    use crate::common::VRPSolution;

    #[derive(Debug)]
    pub struct SolveStats {
        pub iterations: usize,
        pub improvements: Vec<(usize, f64)>,
        pub restarts: Vec<usize>,
        pub cust_change_freq: HashMap<usize, usize>,
        pub route_remove_freq: HashMap<usize, usize>,
        pub route_add_freq: HashMap<usize, usize>,
    }

    impl SolveStats {
        pub fn new() -> Self {
            SolveStats {
                iterations: 0,
                improvements: Vec::new(),
                restarts: Vec::new(),
                cust_change_freq: HashMap::new(),
                route_add_freq: HashMap::new(),
                route_remove_freq: HashMap::new(),
            }
        }

        pub fn update_on_iter(
            &mut self,
            iter: usize,
            new_sol: &VRPSolution,
            improvement_on_best: f64,
        ) {
            if improvement_on_best > 0.01 {
                self.improvements.push((iter, new_sol.cost()));
            }
            self.iterations += 1;
        }

        pub fn on_restart(&mut self, iter: usize) {
            self.restarts.push(iter);
        }
    }
}

#[allow(dead_code)]
type SolveResult = (VRPSolution, SolveStats);

/// Completely solve a VRP instance and return the best solution found.
pub fn solve<S: IterativeSolver>(instance: &Arc<VRPInstance>, params: &SolveParams) -> VRPSolution {
    let initial_solution = (params.constructor)(instance);
    let start_time = std::time::Instant::now();
    let mut solver = S::new(instance.clone(), initial_solution.clone());

    let mut best = initial_solution;
    let mut best_for_jump = best.clone();
    let mut best_cost = best.cost();
    let mut best_cost_for_jump = best.cost();
    let mut stagnant_iterations = 0;
    let mut _iterations_since_prev_new_best = 0;
    let mut last_cost = best.cost();
    let mut rng = rand::rng();

    let mut iters: Box<dyn Iterator<Item = usize>> = match params.terminate {
        TermCond::MaxIters(max) => Box::new(0..max),
        TermCond::TimeElapsed(_) => Box::new(0..),
    };

    let start = Instant::now();
    let mut new_solution = best.clone();
    let mut old_solution = best.clone();
    for iter in &mut iters {
        if let TermCond::TimeElapsed(max_time) = params.terminate {
            if start.elapsed() > max_time {
                break;
            }
        }

        // save old solution first
        old_solution.clone_from(solver.current());

        // get new solution
        let new_solution_res = solver.find_new_solution();

        if new_solution_res.is_none() {
            dbg_println!("failed to produce feasible new solution; reverting to old solution");
            solver.jump_to_solution(&old_solution);
            continue;
        }
        new_solution.clone_from(solver.current());

        let new_cost = new_solution.cost();
        solver
            .get_stats_mut()
            .update_on_iter(iter, &new_solution, best_cost - new_cost);

        if new_cost + 0.1 < best_cost_for_jump {
            best_for_jump.clone_from(&new_solution);
            best_cost_for_jump = new_cost;
        }
        if new_cost + 0.1 < best_cost {
            best.clone_from(&new_solution);
            best_cost = new_cost;
            _iterations_since_prev_new_best = 0;
            dbg_println!("new_best: {}", best_cost);
        } else {
            _iterations_since_prev_new_best += 1;
        }

        if new_cost + 0.1 < last_cost {
            // improvement
            stagnant_iterations = 0;
        } else {
            // no improvement
            stagnant_iterations += 1;

            // simulated annealing — with 0.1 probability, do not revert to the old solution (i.e. accept the new, worse solution)
            if rng.random_bool(0.9) {
                solver.jump_to_solution(&old_solution);
            }
        }
        if iter % 10000 == 0 {
            dbg_println!("iter {:?} has cost {:?}", iter, solver.cost());
        }

        last_cost = new_cost;

        #[allow(clippy::cast_precision_loss)]
        if f64::from(stagnant_iterations) > (params.patience as f64) {
            dbg_println!("Restarting with patience {}...", params.patience);
            stagnant_iterations = 0;

            let new_sol = if rng.random_bool(0.2) {
                dbg_println!("Jumping from current jump best...");
                (params.jumper)(instance, best_for_jump.clone(), params.frac_dropped)
            } else {
                dbg_println!("Jumping from globally found best...");
                (params.jumper)(instance, best.clone(), params.frac_dropped)
            };

            solver.get_stats_mut().on_restart(iter);
            best_cost_for_jump = new_sol.cost();
            best_for_jump.clone_from(&new_sol);
            solver.jump_to_solution(&new_sol);
        }
    }

    let total_iters = match params.terminate {
        TermCond::MaxIters(max) => max,
        TermCond::TimeElapsed(_) => iters.next().unwrap() - 1,
    };

    println!("ran for {:#?}", start_time.elapsed());
    println!("got through {total_iters:?} iters");

    dbg_println!("Stats: {:?}", solver.get_stats_mut());
    best
}

impl<T> IterativeSolver for T
where
    T: LNSSolver,
{
    fn new(instance: Arc<VRPInstance>, initial_solution: VRPSolution) -> Self {
        Self::new(instance, initial_solution)
    }

    fn get_stats_mut(&mut self) -> &mut SolveStats {
        self.get_stats_mut()
    }

    fn current(&self) -> &VRPSolution {
        self.current()
    }

    fn find_new_solution(&mut self) -> Option<()> {
        // let current_sol = self.current(); // clones here
        let destroy_res = self.destroy();
        self.update_tabu(&destroy_res);

        // TOOD: refactor yuckiness here
        let new_sol: Option<()> = match self.repair(destroy_res) {
            // repair has to clone here too...
            Ok(()) => Some(()),
            Err(_) => None,
        };
        // (current_sol, new_sol)
        new_sol
    }

    fn jump_to_solution(&mut self, sol: &VRPSolution) {
        self.jump_to_solution(sol);
    }

    fn cost(&self) -> f64 {
        self.current().cost()
    }
}
