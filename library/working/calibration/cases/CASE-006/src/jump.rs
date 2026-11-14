use std::sync::Arc;

use rand::seq::SliceRandom;

use crate::{
    common::{Stop, VRPSolution},
    dbg_println,
    vrp_instance::VRPInstance,
};

#[allow(clippy::needless_pass_by_value)]
pub fn random_jump(
    vrp_instance: &Arc<VRPInstance>,
    existing: VRPSolution,
    frac_dropped: f64,
) -> VRPSolution {
    for _i in 0..5 {
        if let Ok(sol) = random_drop(vrp_instance, existing.clone(), frac_dropped) {
            return sol;
        }
    }
    panic!("random_jump failed");
}

pub fn random_drop(
    vrp_instance: &Arc<VRPInstance>,
    mut existing: VRPSolution,
    frac_dropped: f64,
) -> Result<VRPSolution, String> {
    dbg_println!(
        "JUMPING (*random drop technique* dropping {:?}%)",
        frac_dropped * 100f64
    );
    let rng = &mut rand::rng();

    #[allow(
        clippy::cast_possible_truncation,
        clippy::cast_sign_loss,
        clippy::cast_precision_loss
    )]
    let to_remove = (vrp_instance.num_customers as f64 * frac_dropped) as usize;

    let mut removed_cust_nos =
        (1..u16::try_from(vrp_instance.num_customers).unwrap()).collect::<Vec<_>>();
    removed_cust_nos.shuffle(rng);
    removed_cust_nos.truncate(to_remove);

    existing.routes.iter_mut().for_each(|r| {
        r.retain_stops(|s| !removed_cust_nos.contains(&s.cust_no()));
    });

    let mut to_add = removed_cust_nos
        .iter()
        .map(|cust_no| Stop::new(*cust_no, vrp_instance.demand_of_customer[*cust_no as usize]))
        .collect::<Vec<_>>();
    to_add.sort_by_key(|t| std::cmp::Reverse(t.capacity()));

    existing.routes.shuffle(rng);

    for s in to_add {
        let mut was_added = false;
        for r in &mut existing.routes {
            if r.used_capacity() + s.capacity() <= vrp_instance.vehicle_capacity {
                let index = r.speculative_add_best(&s).1;
                r.add_stop_to_index(s, index);
                was_added = true;
                r.assert_sanity();
                break;
            }
        }
        if !was_added {
            return Err("didn't work".to_string());
        }
    }

    Ok(existing)
}
