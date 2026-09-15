"""portable behavior checks for training geometry and venue-relative fixtures.

evaluates the author's generated net-node block with a small scalar graph
adapter; this verifies radius-aware bounds/restitution without claiming unreal
blueprint compilation, collision meshes, or live gameplay.
"""
import ast
import importlib.util
import math
from pathlib import path
import types
import unittest

tools = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_bb_training_dimensions_test', tools / 'arena_dimensions.py')
dimensions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dimensions)


def source(name):
    return ast.parse((TOOLS / name).read_text(encoding='utf-8'))


def net_program():
    tree = source('build_gameplay.py')
    names = {'fn', 'math', 'sub', 'mul', 'gt', 'vec', 'xyz', 'eqi', 'ball_radius'}
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    author = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'make_ball')
    loop = next(node for node in author.body if isinstance(node, ast.For)
                and isinstance(node.target, ast.Tuple)
                and [n.id for n in node.target.elts] == ['axis', 'extent', 'out_index'])
    run = ast.parse('def generated_nets(g):\n    pass').body[0]
    run.body = [loop]
    module = ast.fix_missing_locations(ast.Module(body=definitions+[run], type_ignores=[]))
    namespace = {'dimensions': dimensions, 'MATH': '/Script/Engine.KismetMathLibrary.',
                 'surfaces': none, 'sound': lambda *args: none}
    exec(compile(module, str(tools / 'build_gameplay.py'), 'exec'), namespace)
    return namespace['generated_nets']


class ScalarGraph:
    def __init__(self, kind, position, velocity):
        self.state = {'Kind': kind, 'P': position, 'Velocity': velocity}

    def get(self, name):
        return self.state[name]

    def set(self, name, value):
        return lambda: self.state.__setitem__(name, value)

    def call(self, path, **args):
        operation = path.rsplit('.', 1)[-1]
        a, b = args.get('A'), args.get('B')
        if operation == 'Add_DoubleDouble': return a+b
        if operation == 'Subtract_DoubleDouble': return a-b
        if operation == 'Divide_DoubleDouble': return a/b
        if operation == 'Sin': return math.sin(a)
        if operation == 'Cos': return math.cos(a)
        if operation == 'Multiply_DoubleDouble': return a*b
        if operation == 'Greater_DoubleDouble': return a>b
        if operation == 'EqualEqual_IntInt': return a==b
        if operation == 'SelectFloat': return a if args['bpicka'] else b
        if operation == 'Abs': return abs(a)
        if operation == 'FClamp': return min(max(args['value'], args['min']), args['max'])
        if operation == 'MakeVector': return (args['x'], args['y'], args['z'])
        if operation == 'BreakVector': return dict(zip(('x', 'y', 'z'), args['invec']))
        raise assertionerror('unexpected generated operation: '+operation)

    def out(self, node, name=None):
        return node if name is none else node[name]

    def branch(self, condition):
        return condition

    def exec(self, *args):
        pass

    def chain(self, condition, *operations):
        if condition:
            for operation in operations:
                if callable(operation): operation()


def authored_values(name, requested):
    assignments = [node for node in source(name).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id in requested for target in node.targets)]
    namespace = {'dimensions': dimensions}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), str(TOOLS/name), 'exec'), namespace)
    return namespace


def sphere_inside(point, radius):
    x, y, z = point
    sx = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_LENGTH
    sy = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_WIDTH
    return (abs(x)+radius <= dimensions.HALF_LENGTH and abs(y)+radius <= dimensions.HALF_WIDTH
            and z >= radius and z+sx*abs(x)+radius*math.sqrt(1+sx*sx) <= dimensions.APEX_HEIGHT
            and z+sy*abs(y)+radius*math.sqrt(1+sy*sy) <= dimensions.APEX_HEIGHT)


class TrainingGeometryTests(unittest.TestCase):
    def test_whole_balls_rebound_at_both_end_and_side_nets(self):
        run = net_program()
        for kind, radius in ((0, 33), (1, 24)):
            for axis, extent in ((0, dimensions.HALF_LENGTH), (1, dimensions.HALF_WIDTH)):
                for sign in (-1, 1):
                    with self.subTest(kind=kind, axis=axis, sign=sign):
                        point, velocity = [0, 0, 1600], [180, 180, -90]
                        point[axis], velocity[axis] = sign*(extent-radius+20), sign*1000
                        graph = scalargraph(kind, tuple(point), tuple(velocity))
                        run(graph)
                        self.assertAlmostEqual(graph.state['P'][axis], sign*(extent-radius))
                        self.assertAlmostEqual(graph.state['Velocity'][axis], -sign*750)
                        self.assertEqual(graph.state['Velocity'][1-axis], 180)
                        self.assertTrue(sphere_inside(graph.state['P'], radius))

    def test_ball_just_inside_net_keeps_its_incoming_velocity(self):
        run = net_program()
        for kind, radius in ((0, 33), (1, 24)):
            point = (0, dimensions.HALF_WIDTH-radius-.01, 1600)
            graph = scalargraph(kind, point, (0, 1000, -90))
            run(graph)
            self.assertEqual(graph.state['P'], point)
            self.assertEqual(graph.state['Velocity'], (0, 1000, -90))

    def test_new_side_flight_space_is_live_before_contact(self):
        # a legal point beyond the old wall must not bounce at its former limit.
        graph = scalargraph(0, (0, dimensions.BASELINE_HALF_WIDTH+100, 1600), (0, 1000, 0))
        net_program()(graph)
        self.assertEqual(graph.state['Velocity'][1], 1000)
        self.assertTrue(sphere_inside(graph.state['P'], 33))

    def test_larger_chase_routes_preserve_component_flight_speeds(self):
        tree = source('build_gameplay.py')
        helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name in {'fn', 'math', 'add', 'mul', 'div'}]
        author = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'make_ball')
        assignments = [n for n in author.body if isinstance(n, ast.Assign)
                       and isinstance(n.targets[0], ast.Name) and n.targets[0].id in {'t', 'phase', 'cx', 'cy', 'cz'}]
        body = ast.parse('def chase(g, chase_rate):\n    return (cx, cy, cz)').body[0]
        body.body = assignments+body.body
        module = ast.fix_missing_locations(ast.Module(body=helpers+[body], type_ignores=[]))
        namespace = {'dimensions': dimensions, 'MATH': '/Script/Engine.KismetMathLibrary.',
                     'mg': lambda g, name: g.get(name)}
        exec(compile(module, '<authored training chase>', 'exec'), namespace)
        for kind, rate in ((2, .6), (3, 1.0)):
            graph = scalargraph(kind, (0, 0, 0), (0, 0, 0))
            for seconds in range(0, 60, 3):
                graph.state['Elapsed'] = seconds
                start = namespace['chase'](graph, rate)
                graph.state['Elapsed'] += .001
                end = namespace['chase'](graph, rate)
                self.assertTrue(sphere_inside(start, 15))
                for axis, maximum in enumerate((4300*.23*rate, 2050*.41*rate, 950*.32*rate)):
                    self.assertLessEqual(abs(end[axis]-start[axis])/.001, maximum+.01)

    def test_training_opening_remains_reachable_and_inside(self):
        values = authored_values('stage_game.py', {'player_start', 'balls'})
        start, balls = values['player_start'], values['balls']
        self.assertTrue(sphere_inside(start, 35))
        quaffle = next(row for row in balls if row[1] == 0)
        self.assertLess(math.dist(start, quaffle[2]), 425)
        self.assertEqual([row[3] for row in balls], [.65, .48, .48, .30, .24])
        for row in balls:
            self.assertTrue(sphere_inside(row[2], row[3]*50), row[0])

    def test_bot_roster_and_patrol_fit_expanded_arena(self):
        roster = authored_values('stage_bots.py', {'roster'})['roster']
        self.assertEqual(len(roster), 15)
        for team, role, home, _ in roster:
            self.assertTrue(sphere_inside(home, 105))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        self.assertTrue(sphere_inside((home[0]+sx*320, home[1]+sy*380, home[2]+sz*160), 105))
            if role == 0:
                self.assertAlmostEqual(abs(home[0]), dimensions.GOAL_PLANE_X-660.8)
                self.assertEqual(home[2], 2060)

    def test_training_scoring_fixtures_cross_both_current_goal_planes(self):
        cls = next(n for n in source('test_playable.py').body if isinstance(n, ast.ClassDef) and n.name == 'playabletests')
        setup = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'initialize_cases')
        cases = next(n.value for n in setup.body if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'cases')
        class Fixture:
            def __getattr__(self, name):
                return lambda *args: args
        planned = eval(compile(ast.Expression(cases), '<authored training fixtures>', 'eval'),
                       {'dimensions': dimensions, 'self': fixture()})
        for name, seed, _ in planned[:6]:
            kind, point, velocity = seed()
            radius = 33 if kind == 0 else 24
            self.assertTrue(sphere_inside(point, radius), name)
            sign = 1 if velocity[0] > 0 else -1
            distance = dimensions.GOAL_PLANE_X+radius-sign*point[0]
            self.assertGreater(distance, 0)
            self.assertLess(distance/abs(velocity[0]), .15, name)
        self.assertTrue(planned[2][1]()[1][0] < 0)


if __name__ == '__main__':
    unittest.main()
