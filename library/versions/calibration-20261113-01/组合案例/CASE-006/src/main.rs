mod common;
mod construct;
mod jump;
mod solver;
pub mod solvers;
mod swap;
mod vrp_instance;

use solver::{SolveParams, TermCond};
use std::time::Duration;
use std::{env, sync::Arc, time::Instant};
use vrp_instance::VRPInstance;

use serde_json::json;
use std::fs::File;
use std::io::Write;
use std::path::Path;

fn get_filename_from_path(path: &str) -> &str {
    Path::new(path)
        .file_name()
        .and_then(|filename| filename.to_str())
        .unwrap_or("")
}

fn main() {
    // Check if a file name was provided as a command-line argument
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        // If no arguments provided, run the test
        return;
    }

    let file_path = &args[1];
    let file_name = get_filename_from_path(file_path);

    let start = Instant::now();
    let vrp_instance = VRPInstance::new(file_path);
    let frac_dropped = 0.0;
    // let patience = (vrp_instance.num_customers as f64 * frac_dropped) as usize;
    let patience = 50;

    // 26.5k

    let vrp_instance = Arc::new(vrp_instance);
    let params = SolveParams {
        // terminate: TermCond::MaxIters(50000),
        terminate: TermCond::TimeElapsed(Duration::from_secs(15)),
        frac_dropped,
        patience,
        constructor: construct::clarke_wright_and_then_sweep,
        jumper: jump::random_jump,
    };
    let sol = solver::solve::<solvers::MultiLNSSolver>(&vrp_instance, &params);
    let duration = start.elapsed();

    let output = json!({
        "Instance": file_name,
        "Time": (duration.as_secs_f64() * 100.0).round() / 100.0,
        "Result": sol.cost(),
        "Solution": sol.to_string(),
    });

    println!("{}", serde_json::to_string(&output).unwrap());

    let sol_path = &format!("./{file_name}.sol");
    let path = Path::new(sol_path);
    let mut file = File::create(path).unwrap();

    // Write the string to the file
    file.write_all(sol.to_file_string().as_bytes()).unwrap();
}
