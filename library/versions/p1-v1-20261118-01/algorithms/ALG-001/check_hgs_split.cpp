#include "hgs_split/Split.h"

#include <cmath>
#include <iostream>
#include <string>

bool check(const char* name, const Individual& individual, int routes,
           double distance, double capacityExcess, double durationExcess,
           double penalizedCost)
{
    const CostSol& cost = individual.myCostSol;
    const std::vector<std::vector<int>> expected = {{1}, {2, 3}, {}};
    bool ok = individual.chromR == expected
        && cost.nbRoutes == routes
        && std::abs(cost.distance - distance) < 1.e-8
        && std::abs(cost.capacityExcess - capacityExcess) < 1.e-8
        && std::abs(cost.durationExcess - durationExcess) < 1.e-8
        && std::abs(cost.penalizedCost - penalizedCost) < 1.e-8
        && individual.isFeasible == (capacityExcess == 0. && durationExcess == 0.);
    std::cout << name << (ok ? ": PASS" : ": FAIL")
              << " routes=" << cost.nbRoutes << " distance=" << cost.distance
              << " capacity_excess=" << cost.capacityExcess
              << " duration_excess=" << cost.durationExcess
              << " cost=" << cost.penalizedCost << '\n';
    return ok;
}

int main(int argc, char** argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: check_hgs_split <check_hgs_split.vrp>\n";
        return 2;
    }
    Params params(argv[1], 3, 0);
    params.penaltyCapacity = 100.;
    params.penaltyDuration = 10.;
    Individual individual(&params);
    individual.chromT = {1, 2, 3};
    Split split(&params);

    split.generalSplit(&individual, 2);
    bool ok = check("simple", individual, 2, 44., 0., 0., 44.);

    // 三名客户各需 4，普通 Split 需要三辆车；限制为两辆时应进入有限车队分支。
    for (int i = 1; i <= params.nbClients; ++i) params.cli[i].demand = 4.;
    params.totalDemand = 12.;
    split.generalSplit(&individual, 2);
    ok = check("limited fleet", individual, 2, 44., 2., 0., 244.) && ok;

    for (int i = 1; i <= params.nbClients; ++i) params.cli[i].demand = 3.;
    params.totalDemand = 9.;
    params.isDurationConstraint = true;
    params.durationLimit = 20.;
    split.generalSplit(&individual, 2);
    ok = check("duration", individual, 2, 44., 0., 4., 84.) && ok;
    return ok ? 0 : 1;
}
