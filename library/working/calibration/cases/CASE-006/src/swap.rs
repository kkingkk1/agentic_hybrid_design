use crate::common::Stop;

pub struct SwapResult {
    pub a_route_i: usize,
    pub a_i: usize,
    pub a_stop: Stop,

    pub b_route_i: usize,
    pub b_i: usize,
    pub b_stop: Stop,
}

impl std::fmt::Debug for SwapResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_fmt(format_args!(
            "SWAP[{:?} (was @ {:?} in {:?}) <-> {:?} (was @ {:?} in {:?})]",
            self.a_stop, self.a_i, self.a_route_i, self.b_stop, self.b_i, self.b_route_i
        ))
    }
}

pub mod single_swap {
    use std::sync::Arc;

    use rand::seq::SliceRandom;

    use crate::{common::VRPSolution, vrp_instance::VRPInstance};

    use super::SwapResult;
    use rand::rng;

    #[allow(dead_code)]
    fn naive_random(_sol: &VRPSolution) -> (VRPSolution, SwapResult) {
        todo!()
    }

    #[allow(dead_code)]
    pub fn naive_greedy(
        mut sol: VRPSolution,
        vrp_instance: &Arc<VRPInstance>,
    ) -> (VRPSolution, Option<SwapResult>) {
        let mut rng = rng();
        // shuffle routes
        sol.routes.shuffle(&mut rng);

        let mut swap = None;

        'full_loop: for (a_route_i, a_route) in sol.routes.iter().enumerate() {
            for (b_route_i, b_route) in sol.routes.iter().enumerate() {
                if a_route_i <= b_route_i {
                    continue;
                }

                let initial_cost = a_route.cost() + b_route.cost();
                for (a_i, a) in a_route.stops().iter().enumerate() {
                    for (b_i, b) in b_route.stops().iter().enumerate() {
                        let a_under_cap = a_route.used_capacity() - a.capacity() + b.capacity()
                            <= vrp_instance.vehicle_capacity;
                        let b_under_cap = b_route.used_capacity() - b.capacity() + a.capacity()
                            <= vrp_instance.vehicle_capacity;

                        if !a_under_cap || !b_under_cap {
                            continue;
                        }

                        let new_cost = a_route.cost_if_cust_no_was(b, a_i)
                            + b_route.cost_if_cust_no_was(a, b_i);

                        if new_cost < initial_cost {
                            if (initial_cost - new_cost).abs() < 0.01 {
                                continue;
                            }

                            swap = Some(SwapResult {
                                a_route_i,
                                a_i,
                                a_stop: *a,
                                b_route_i,
                                b_i,
                                b_stop: *b,
                            });

                            break 'full_loop;
                        }
                    }
                }
            }
        }

        if let Some(SwapResult {
            a_route_i,
            a_i,
            a_stop: _,
            b_route_i,
            b_i,
            b_stop: _,
        }) = swap
        {
            let a = sol.routes[a_route_i].remove_stop_at_index(a_i);
            let b = sol.routes[b_route_i].remove_stop_at_index(b_i);

            sol.routes[a_route_i].add_stop_to_index(b, a_i);
            sol.routes[b_route_i].add_stop_to_index(a, b_i);
        } else {
            return (sol, None);
        }

        (sol, swap)
    }
}
