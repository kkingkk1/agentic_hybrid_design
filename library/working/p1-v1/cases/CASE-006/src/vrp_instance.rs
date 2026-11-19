use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process;

use crate::common::DistanceMatrix;
use crate::dbg_println;

pub struct VRPInstance {
    pub num_customers: usize,
    pub num_vehicles: usize,
    pub vehicle_capacity: usize,
    pub demand_of_customer: Vec<usize>,
    pub x_coord_of_customer: Vec<f64>,
    pub y_coord_of_customer: Vec<f64>,
    pub distance_matrix: DistanceMatrix,
    pub max_route_len: usize,
}

impl VRPInstance {
    pub fn new<P: AsRef<Path>>(file_name: P) -> Self {
        let lines = Self::read_lines_from_file(&file_name);

        let (num_customers, num_vehicles, vehicle_capacity) =
            Self::parse_first_line(&lines[0], &file_name);

        // Initialize arrays for customer data
        let mut demand_of_customer = vec![0; num_customers];
        let mut x_coord_of_customer = vec![0.0; num_customers];
        let mut y_coord_of_customer = vec![0.0; num_customers];

        // Parse customer data
        for i in 0..num_customers {
            if i + 1 < lines.len() {
                let customer_data: Vec<&str> = lines[i + 1].split_whitespace().collect();
                if customer_data.len() < 3 {
                    eprintln!(
                        "Error: in VRPInstance() {}\nInvalid customer data format at line {}",
                        file_name.as_ref().display(),
                        i + 2
                    );
                    process::exit(-1);
                }

                demand_of_customer[i] = customer_data[0].parse::<usize>().unwrap_or_else(|e| {
                    eprintln!("Error parsing customer demand: {e}");
                    process::exit(-1);
                });

                x_coord_of_customer[i] = customer_data[1].parse::<f64>().unwrap_or_else(|e| {
                    eprintln!("Error parsing x coordinate: {e}");
                    process::exit(-1);
                });

                y_coord_of_customer[i] = customer_data[2].parse::<f64>().unwrap_or_else(|e| {
                    eprintln!("Error parsing y coordinate: {e}");
                    process::exit(-1);
                });
            }
        }

        // Print customer data
        for i in 0..num_customers {
            dbg_println!(
                "{} {} {}",
                demand_of_customer[i],
                x_coord_of_customer[i],
                y_coord_of_customer[i]
            );
        }

        let distance_matrix: Vec<Vec<f64>> = (0..num_customers)
            .map(|i| {
                (0..num_customers)
                    .map(|j| {
                        ((x_coord_of_customer[i] - x_coord_of_customer[j]).powi(2)
                            + (y_coord_of_customer[i] - y_coord_of_customer[j]).powi(2))
                        .sqrt()
                    })
                    .collect()
            })
            .collect();

        VRPInstance {
            num_customers,
            num_vehicles,
            vehicle_capacity,
            max_route_len: Self::max_route_len(&demand_of_customer, vehicle_capacity),
            demand_of_customer,
            x_coord_of_customer,
            y_coord_of_customer,
            distance_matrix: DistanceMatrix::new(distance_matrix),
        }
    }

    #[allow(dead_code)]
    pub fn to_string(&self) {
        dbg_println!("Number of customers: {}", self.num_customers);
        dbg_println!("Number of vehicles: {}", self.num_vehicles);
        dbg_println!("Vehicle capacity: {}", self.vehicle_capacity);
    }

    pub fn max_route_len(demands: &[usize], capacity: usize) -> usize {
        let mut demands = demands.to_owned();
        demands.swap_remove(0);
        demands.sort_unstable();
        let mut used_cap = 0;
        let mut count = 0;

        for d in demands {
            if used_cap >= capacity {
                break;
            }
            count += 1;
            used_cap += d;
        }

        count
    }

    fn read_lines_from_file<P: AsRef<Path>>(file_name: P) -> Vec<String> {
        let Ok(file) = File::open(&file_name) else {
            eprintln!(
                "Error: in VRPInstance() {}\nFile not found",
                file_name.as_ref().display()
            );
            process::exit(-1);
        };

        let reader = BufReader::new(file);
        let lines: Vec<String> = reader
            .lines()
            .map(|line| {
                line.unwrap_or_else(|e| {
                    eprintln!("Error reading line: {e}");
                    process::exit(-1);
                })
            })
            .collect();

        if lines.is_empty() {
            eprintln!(
                "Error: in VRPInstance() {}\nFile is empty",
                file_name.as_ref().display()
            );
            process::exit(-1);
        }
        lines
    }

    fn parse_first_line<P: AsRef<Path>>(line: &str, file_name: P) -> (usize, usize, usize) {
        let first_line: Vec<&str> = line.split_whitespace().collect();
        if first_line.len() < 3 {
            eprintln!(
                "Error: in VRPInstance() {}\nInvalid first line format",
                file_name.as_ref().display()
            );
            process::exit(-1);
        }

        let num_customers = first_line[0].parse::<usize>().unwrap_or_else(|e| {
            eprintln!("Error parsing number of customers: {e}");
            process::exit(-1);
        });

        let num_vehicles = first_line[1].parse::<usize>().unwrap_or_else(|e| {
            eprintln!("Error parsing number of vehicles: {e}");
            process::exit(-1);
        });

        let vehicle_capacity = first_line[2].parse::<usize>().unwrap_or_else(|e| {
            eprintln!("Error parsing vehicle capacity: {e}");
            process::exit(-1);
        });
        (num_customers, num_vehicles, vehicle_capacity)
    }
}
