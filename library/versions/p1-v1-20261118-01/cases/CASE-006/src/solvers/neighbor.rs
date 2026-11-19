use std::{
    collections::{HashMap, VecDeque},
    sync::Arc,
};

use rand::{Rng, rng};

use crate::common::{Stop, VRPSolution};
use crate::solver::LNSSolver;
use crate::solver::stats::SolveStats;
use crate::vrp_instance::VRPInstance;

/// An LNS solver which greedily **removes the highest cost stop** from the solution,
/// **inserting it at the lowest cost location**.
pub struct SimpleLNSSolver {
    instance: Arc<VRPInstance>,
    stop_tabu: VecDeque<Stop>,
    current: VRPSolution,
    moves: HashMap<Stop, usize>,
    stats: SolveStats,
}

impl LNSSolver for SimpleLNSSolver {
    /// corresponding to the (stop, route #) that was removed
    type DestroyResult = (Stop, usize);

    fn new(instance: Arc<VRPInstance>, initial_solution: VRPSolution) -> Self {
        SimpleLNSSolver {
            stop_tabu: VecDeque::new(),
            current: initial_solution,
            moves: HashMap::new(),
            instance,
            stats: SolveStats::new(),
        }
    }

    fn current(&self) -> &VRPSolution {
        &self.current
    }

    fn destroy(&mut self) -> Self::DestroyResult {
        let (stop, route_idx) = self.remove_random_stop();
        *self
            .stats
            .cust_change_freq
            .entry(stop.cust_no().into())
            .or_insert(0) += 1;
        *self.stats.route_remove_freq.entry(route_idx).or_insert(0) += 1;
        (stop, route_idx)
    }

    fn get_stats_mut(&mut self) -> &mut SolveStats {
        &mut self.stats
    }

    fn repair(&mut self, res: Self::DestroyResult) -> Result<(), String> {
        let route_idx = Self::reinsert_in_best_spot(&mut self.current, res.0);
        *self.stats.route_add_freq.entry(route_idx).or_insert(0) += 1;
        Ok(())
    }

    fn jump_to_solution(&mut self, sol: &VRPSolution) {
        self.current.clone_from(sol);
    }

    fn update_tabu(&mut self, res: &Self::DestroyResult) {
        self.stop_tabu.push_back(res.0);
        if self.stop_tabu.len() >= (self.instance.num_customers / 10) {
            self.stop_tabu.pop_front();
        }

        *self.moves.entry(res.0).or_insert(0) += 1;
        let mut move_history = self.moves.iter().collect::<Vec<(&Stop, &usize)>>();
        move_history.sort_by(|a, b| a.1.cmp(b.1));
    }
}

impl SimpleLNSSolver {
    fn remove_random_stop(&mut self) -> (Stop, usize) {
        let tabu = &self.stop_tabu;
        let sol = &mut self.current;

        let mut feas_vals = Vec::new();
        for (r, route) in sol.routes.iter().enumerate() {
            for i in 0..(route.stops().len()) {
                if tabu.contains(&route.stops()[i]) {
                    continue;
                }
                feas_vals.push((r, i));
            }
        }

        let (chosen_spot_r, chosen_spot_i) = *feas_vals
            .get(rng().random_range(0..feas_vals.len()))
            .unwrap();
        let res = sol.routes[chosen_spot_r].remove_stop_at_index(chosen_spot_i);
        (res, chosen_spot_r)
    }

    fn reinsert_in_best_spot(sol: &mut VRPSolution, stop: Stop) -> usize {
        let (mut best_spot_r, mut best_spot_i, mut best_spot_cost_increase) =
            (100_000, 100_000, f64::MAX);

        let mut valid = Vec::new();

        for (r, route) in sol.routes.iter().enumerate() {
            for i in 0..=route.stops().len() {
                let (new_cost, feas) = route.speculative_add_stop(&stop, i);

                // we want the one that will increase the new cost by the least, so minimize
                let cost_increase = new_cost - route.cost();
                if feas {
                    valid.push((r, i));
                }
                if feas && cost_increase < best_spot_cost_increase {
                    (best_spot_r, best_spot_i) = (r, i);
                    best_spot_cost_increase = cost_increase;
                }
            }
        }

        if rng().random_bool(0.02_f64) {
            let i = rng().random_range(0..valid.len());
            (best_spot_r, best_spot_i) = *valid.get(i).unwrap();
        }
        sol.routes[best_spot_r].add_stop_to_index(stop, best_spot_i);
        best_spot_r
    }
}
