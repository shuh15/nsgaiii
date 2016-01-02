import copy,random
import numpy as np
from deap import tools

# from deap import algorithms, base, benchmarks, tools, creator

class ReferencePoint(list):
    def __init__(self, *args):
        list.__init__(self, *args)
        self.associations_count = 0
        self.associations = []

def generate_reference_points(num_objs, num_divisions_per_obj=4):
    '''
    Generates reference points for NSGA-III.
    Based on the code of jMetal which is based on the code of
    Tsung-Che Chiang
    http://web.ntnu.edu.tw/~tcchiang/publications/nsga3cpp/nsga3cpp.htm
    '''
    def gen_refs_recursive(work_point, num_objs, left, total, depth):
        if depth == num_objs - 1:
            work_point[depth] = left/total
            ref = ReferencePoint(copy.deepcopy(work_point))
            return [ref]
        else:
            res = []
            for i in range(left):
                work_point[depth] = i/total
                res = res + gen_refs_recursive(work_point, num_objs, left-i, total, depth+1)
            return res
    return gen_refs_recursive([0]*num_objs, num_objs, num_objs*num_divisions_per_obj,
                              num_objs*num_divisions_per_obj, 0)

def find_ideal_point(individuals):
    current_ideal = [np.infty] * len(individuals[0].fitness.values)
    for ind in individuals:
        current_ideal = np.minimum(current_ideal, ind.fitness.values)
    return current_ideal

def find_extreme_points(individuals):
    return [sorted(individuals, key=lambda ind:ind.fitness.values[o])[-1]
            for o in range(len(individuals[0].fitness.values))]

def has_duplicate_individuals(individuals):
    for i in range(len(individuals)):
        for j in range(i+1, len(individuals)):
            if individuals[i].fitness.values == individuals[j].fitness.values:
                return True
    return False

def construct_hyperplane(individuals, extreme_points):
    num_objs = len(individuals[0].fitness.values)

    if has_duplicate_individuals(extreme_points):
        intercepts = [extreme_points[m].fitness.values[m] for m in range(num_objs)]
    else:
        b = np.ones(num_objs)
        A = [point.fitness.values for point in extreme_points]
        x = np.linalg.solve(A,b)
        intercepts = 1/x
    return intercepts

def normalize_objective(individual, m, intercepts, ideal_point, epsilon=1e-20):
    if np.abs(intercepts[m]-ideal_point[m] > epsilon):
        return individual.fitness.values[m] / (intercepts[m]-ideal_point[m])
    else:
        return individual.fitness.values[m] / epsilon

def normalize_objectives(individuals, intercepts, ideal_point):
    num_objs = len(individuals[0].fitness.values)

    for ind in individuals:
        ind.fitness.normalized_values = list([normalize_objective(ind, m,
                                                                  intercepts, ideal_point)
                                                                  for m in range(num_objs)])
    return individuals

def perpendicular_distance(direction, point):
    k = np.dot(direction, point) / np.sum(np.power(direction, 2))
    d = np.sum(np.power(np.subtract(np.multiply(direction, [k] * len(direction)), point) , 2))
    return np.sqrt(d)

def associate(individuals, reference_points):
    'Associates individuals to reference points and calculates niche number.'
    pareto_fronts = tools.sortLogNondominated(individuals, len(individuals))
    num_objs = len(individuals[0].fitness.values)

    for ind in individuals:
        rp_dists = [(rp, perpendicular_distance(ind.fitness.normalized_values, rp))
                    for rp in reference_points]
        best_rp, best_dist = sorted(rp_dists, key=lambda rpd:rpd[1])[0]
        ind.reference_point = best_rp
        ind.ref_point_distance = best_dist
        best_rp.associations_count +=1 # update de niche number
        best_rp.associations += [ind]

def niching_select(individuals, k):
    if len(individuals) == k:
        return individuals

    #individuals = copy.deepcopy(individuals)

    ideal_point = find_ideal_point(individuals)
    extremes = find_extreme_points(individuals)
    intercepts = construct_hyperplane(individuals, extremes)
    normalize_objectives(individuals, intercepts, ideal_point)

    reference_points = generate_reference_points(len(individuals[0].fitness.values))

    associate(individuals, reference_points)

    res = []
    while len(res) < k:
        min_assoc_rp = min(reference_points, key=lambda rp: rp.associations_count)
        min_assoc_rps = [rp for rp in reference_points if rp.associations_count == min_assoc_rp.associations_count]
        chosen_rp = min_assoc_rps[random.randint(0, len(min_assoc_rps)-1)]

        #print('Rps',min_assoc_rp.associations_count, chosen_rp.associations_count, len(min_assoc_rps))

        associated_inds = chosen_rp.associations

        if chosen_rp.associations:
            if chosen_rp.associations_count == 0:
                sel = min(chosen_rp.associations, key=lambda ind: ind.ref_point_distance)
            else:
                sel = chosen_rp.associations[random.randint(0, len(chosen_rp.associations)-1)]
            res += [sel]
            chosen_rp.associations.remove(sel)
            chosen_rp.associations_count += 1
            individuals.remove(sel)
        else:
            reference_points.remove(chosen_rp)
    return res

def sel_nsga_iii(individuals, k):
    if len(individuals)==k:
        return individuals

    fronts = tools.sortLogNondominated(individuals, len(individuals))

    limit = 0
    res =[]
    for f, front in enumerate(fronts):
        res += front
        if len(res) > k:
            limit = f
            break

    selection = []
    if limit > 0:
        for f in range(limit):
            selection += fronts[f]

    selection += niching_select(fronts[limit], k - len(selection))
    return selection