use std::{cmp::Reverse, collections::VecDeque, sync::Arc};

use rand::{Rng, rng, rngs::ThreadRng};

use crate::common::{Stop, VRPSolution};
use crate::solver::LNSSolver;
use crate::solver::stats::SolveStats;
use crate::vrp_instance::VRPInstance;

/// An LNS solver which greedily **removes the highest cost stop** from the solution,
/// **inserting it at the lowest cost location**.
pub struct MultiLNSSolver {
    instance: Arc<VRPInstance>,
    stop_tabu: VecDeque<usize>,
    stop_not_tabu: Vec<usize>,
    current: VRPSolution,
    stats: SolveStats,
    rng: ThreadRng,
}

impl LNSSolver for MultiLNSSolver {
    /// corresponding to the (`cust_no`, route #) that was removed
    type DestroyResult = Vec<(Stop, usize)>;

    fn new(instance: Arc<VRPInstance>, initial_solution: VRPSolution) -> Self {
        MultiLNSSolver {
            stop_tabu: VecDeque::new(),
            current: initial_solution,
            stop_not_tabu: (1..instance.num_customers).collect(),
            instance,
            stats: SolveStats::new(),
            rng: rand::rng(),
        }
    }

    fn current(&self) -> &VRPSolution {
        &self.current
    }

    fn destroy(&mut self) -> Self::DestroyResult {
        let removed_stops = self.remove_n_random_stops(5);

        for (stop, route_idx) in &removed_stops {
            *self
                .stats
                .cust_change_freq
                .entry(stop.cust_no().into())
                .or_insert(0) += 1;
            *self.stats.route_remove_freq.entry(*route_idx).or_insert(0) += 1;
        }
        removed_stops
    }

    fn get_stats_mut(&mut self) -> &mut SolveStats {
        &mut self.stats
    }

    fn repair(&mut self, res: Self::DestroyResult) -> Result<(), String> {
        let route_idxs = self.reinsert_n_stops_in_best_spots(&res)?;

        for route_idx in route_idxs {
            *self.stats.route_add_freq.entry(route_idx).or_insert(0) += 1;
        }
        Ok(())
    }

    fn jump_to_solution(&mut self, sol: &VRPSolution) {
        self.current.clone_from(sol);
        self.stop_not_tabu = (1..self.instance.num_customers).collect();
        self.stop_tabu.clear();
    }

    fn update_tabu(&mut self, res: &Self::DestroyResult) {
        for (stop, _) in res {
            let cust_no = stop.cust_no().into();
            self.stop_tabu.push_back(cust_no);
        }

        while self.stop_tabu.len() > (self.instance.num_customers / 10) {
            let allowed = self.stop_tabu.pop_front();
            if let Some(allowed) = allowed {
                self.stop_not_tabu.push(allowed);
            }
        }
    }
}

impl MultiLNSSolver {
    fn remove_n_random_stops(&mut self, n: usize) -> Vec<(Stop, usize)> {
        assert!(n > 0);
        self.assert_tabu_sanity();

        let sol = &mut self.current;

        let mut customer_nos = Vec::new();
        for _ in 0..n {
            let rem_index = self.rng.random_range(0..self.stop_not_tabu.len());
            customer_nos.push(self.stop_not_tabu.swap_remove(rem_index));
        }
        assert!(customer_nos.len() == n);

        let mut res = Vec::new();

        for cust_no in customer_nos {
            for (route_idx, route) in sol.routes.iter_mut().enumerate() {
                if let Some(index) = route.index_of_stop(u16::try_from(cust_no).unwrap()) {
                    let removed_stop = route.remove_stop_at_index(index);
                    res.push((removed_stop, route_idx));
                    break;
                }
            }
        }
        res
    }

    #[cfg(debug_assertions)]
    fn assert_tabu_sanity(&self) {
        let full_tabu = self
            .stop_tabu
            .iter()
            .chain(self.stop_not_tabu.iter())
            .collect::<Vec<_>>();

        assert!(full_tabu.len() == (self.instance.num_customers - 1));
        for cust_no in 1..self.instance.num_customers {
            assert!(full_tabu.contains(&&cust_no));
        }
    }
    #[cfg(not(debug_assertions))]
    #[allow(clippy::unused_self)]
    fn assert_tabu_sanity(&self) {}

    fn reinsert_n_stops_in_best_spots(
        &mut self,
        removed_stops: &[(Stop, usize)],
    ) -> Result<Vec<usize>, String> {
        let mut res = Vec::new();
        let mut removed_stops = removed_stops.to_owned();
        removed_stops.sort_by_key(|x| Reverse(x.0.capacity()));
        for (stop, _) in removed_stops {
            res.push(self.reinsert_in_best_spot(stop)?);
        }
        Ok(res)
    }

    fn reinsert_in_best_spot(&mut self, stop: Stop) -> Result<usize, String> {
        let (mut best_spot_r, mut best_spot_i, mut best_spot_cost_increase) =
            (usize::MAX, usize::MAX, f64::MAX);

        // OPT: use with_capacity here to avoid continuous reallocation on push
        let mut valid = Vec::with_capacity(self.instance.num_customers);

        for (r, route) in self.current.routes.iter().enumerate() {
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
        if best_spot_r == usize::MAX {
            return Err("no place to put customer".to_string());
        }

        if rng().random_bool(0.02_f64) {
            let i = rng().random_range(0..valid.len());
            (best_spot_r, best_spot_i) = *valid.get(i).unwrap();
        }
        self.current.routes[best_spot_r].add_stop_to_index(stop, best_spot_i);

        Ok(best_spot_r)
    }
}
