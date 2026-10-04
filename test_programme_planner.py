"""Planner constraint, identity, boundary and API regression tests; no model calls."""
import unittest
from copy import deepcopy
from pydantic import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from programme_planner import Catalogue, DifficultyMix, DIFFICULTY_PRESETS, difficulty_targets, Entry, FigureRule, Options, ProgrammeRequest, catalogue, check, generate, import_programme
from programme_routes import router


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cat=catalogue()

    def id(self,name):
        found=self.cat.names[__import__('programme_planner').normalise(name)]
        self.assertEqual(len(found),1)
        return next(iter(found))

    def entry(self,name,**kwargs):return Entry(dance_id=self.id(name),name=name,**kwargs)

    def test_generate_counts_unique_and_reproducible(self):
        for seed in (2,19,94):
            req=ProgrammeRequest(seed=seed)
            a=generate(req,self.cat);b=generate(req,self.cat)
            self.assertEqual(a['entries'],b['entries'])
            self.assertEqual(a['summary']['rhythms'],{'J':5,'R':6,'S':5})
            main=[e for e in a['entries'] if e['kind']=='dance']
            self.assertEqual(len({e['dance_id'] for e in main}),16)
            self.assertFalse(a['summary']['errors'])

    def test_locks_and_extra_survive_generation(self):
        first=generate(ProgrammeRequest(seed=17),self.cat)
        entries=[Entry(**e) for e in first['entries']]
        entries[2].locked=True;entries[13].locked=True
        extra=self.entry('The Machine without Horses',kind='extra');entries.append(extra)
        result=generate(ProgrammeRequest(entries=entries,seed=82),self.cat)
        self.assertEqual(result['entries'][2]['dance_id'],entries[2].dance_id)
        self.assertEqual(result['entries'][13]['dance_id'],entries[13].dance_id)
        self.assertEqual(result['entries'][-1]['kind'],'extra')
        self.assertEqual(result['entries'][-1]['dance_id'],extra.dance_id)

    def test_locked_rhythm_conflict_explained(self):
        entries=[self.entry('The Machine without Horses',locked=True),self.entry("Hooper's Jig",locked=True)]
        with self.assertRaisesRegex(ValueError,'cannot avoid'):
            generate(ProgrammeRequest(entries=entries),self.cat)

    def test_unknown_locked_dance_cannot_be_replaced_silently(self):
        with self.assertRaisesRegex(ValueError,'Identify every locked'):
            generate(ProgrammeRequest(entries=[Entry(name='unknown',locked=True)]),self.cat)

    def test_mismatched_counts_not_silently_adjusted(self):
        with self.assertRaisesRegex(ValueError,'add up'):
            generate(ProgrammeRequest(options=Options(jigs=6)),self.cat)

    def test_break_unknown_and_extra_do_not_create_neighbours(self):
        jig=self.entry('The Machine without Horses');jig2=self.entry("Hooper's Jig")
        for separator in [Entry(kind='break',name='Interval'),Entry(name='unknown'),self.entry('The Minister on the Loch',kind='extra')]:
            result=check(ProgrammeRequest(entries=[jig,separator,jig2]),self.cat)
            self.assertEqual(result['summary']['eligible_rhythm_pairs'],0)
            self.assertNotIn('rhythm_neighbours',[x['code'] for x in result['issues']])
        result=check(ProgrammeRequest(entries=[jig,jig2]),self.cat)
        self.assertIn('rhythm_neighbours',[x['code'] for x in result['issues']])

    def test_main_duplicate_is_not_an_extra_duplicate(self):
        dance=self.entry('The Machine without Horses')
        a=check(ProgrammeRequest(entries=[dance,dance]),self.cat)
        b=check(ProgrammeRequest(entries=[dance,dance.model_copy(update={'kind':'extra'})]),self.cat)
        self.assertIn('duplicate',[i['code'] for i in a['issues']])
        self.assertNotIn('duplicate',[i['code'] for i in b['issues']])

    def test_import_preserves_unknown_and_ambiguous_names(self):
        result=import_programme('1. The Machine without Horses;Made up dance;Interval;Extras;The Reel of the 51st Division',self.cat)
        self.assertEqual([x['kind'] for x in result],['dance','dance','break','extra'])
        self.assertIsNone(result[1]['dance_id'])
        ambiguous=next(name for name,ids in self.cat.names.items() if len(ids)>1)
        self.assertIsNone(import_programme(ambiguous,self.cat)[0]['dance_id'])

    def test_import_own_export_format(self):
        result=import_programme('1. The Machine without Horses — J32\nInterval\nExtras\nThe Reel of the 51st Division — R32',self.cat)
        self.assertEqual(result[0]['dance_id'],self.id('The Machine without Horses'))
        self.assertEqual(result[2]['dance_id'],self.id('The Reel of the 51st Division'))

    def test_figure_constraints_count_and_gap_with_boundary(self):
        d=next(d for d in self.cat.dances.values() if 'ALLMND' in d['families'])
        e=Entry(dance_id=d['id'],name=d['name'])
        o=Options(duplicate_mode='off',figure_rules=[FigureRule(key='family:ALLMND',max_count=1,min_gap=2)])
        a=check(ProgrammeRequest(entries=[e,e],options=o),self.cat)
        self.assertIn('figure_count',[x['code'] for x in a['issues']]);self.assertIn('figure_gap',[x['code'] for x in a['issues']])
        b=check(ProgrammeRequest(entries=[e,Entry(kind='break'),e],options=o),self.cat)
        self.assertIn('figure_count',[x['code'] for x in b['issues']]);self.assertNotIn('figure_gap',[x['code'] for x in b['issues']])

    def test_hard_figure_generation_and_missing_coverage(self):
        rule=FigureRule(key='family:ALLMND',max_count=0,mode='error')
        result=generate(ProgrammeRequest(options=Options(figure_rules=[rule]),seed=21),self.cat)
        self.assertFalse(result['summary']['errors'])
        for e in result['entries']:
            if e['kind']=='dance':
                d=self.cat.dances[e['dance_id']];self.assertEqual(d['formations_verified'],1);self.assertNotIn('ALLMND',d['families'])
        unknown=next(d for d in self.cat.dances.values() if d['formations_verified']!=1)
        result=check(ProgrammeRequest(entries=[Entry(dance_id=unknown['id'])],options=Options(figure_rules=[rule])),self.cat)
        self.assertIn('figure_unverified',[x['code'] for x in result['issues']])

    def test_locked_beyond_shortened_programme_fails(self):
        entries=[self.entry('The Machine without Horses') for _ in range(5)];entries[-1].locked=True
        with self.assertRaisesRegex(ValueError,'beyond the requested length'):
            generate(ProgrammeRequest(entries=entries,options=Options(length=4,jigs=1,reels=2,strathspeys=1,break_after=2)),self.cat)

    def test_no_generated_rule_violations_across_lengths(self):
        for n in (4,8,18,24,32):
            s=round(n/3);j=(n-s)//2;r=n-s-j
            result=generate(ProgrammeRequest(options=Options(length=n,jigs=j,reels=r,strathspeys=s,break_after=n//2),seed=n),self.cat)
            self.assertEqual(result['summary']['main_count'],n)
            self.assertEqual(result['summary']['errors'],0)

    def test_published_difficulty_metadata(self):
        for grade in (1,2,3,4,None):
            dance=next(d for d in self.cat.dances.values() if d['rscds_grade']==grade)
            public=self.cat.public(dance)
            self.assertEqual(public['rscds_grade'],grade)
            self.assertIsNone(public['difficulty_estimate'])
            if grade==4:
                self.assertIn('Expert-level',public['rscds_grade_label'])
                self.assertNotIn('ghillies',public['rscds_grade_label'])
            elif grade is None:self.assertIsNone(public['rscds_grade_label'])

    def test_difficulty_balances_across_pools_and_profiles(self):
        for pool in ('sample','catalogue'):
            for profile,mix in DIFFICULTY_PRESETS.items():
                for seed in (8,81):
                    o=Options(difficulty_mix=mix,pool=pool)
                    result=generate(ProgrammeRequest(options=o,seed=seed),self.cat)
                    self.assertEqual(result['summary']['errors'],0)
                    self.assertEqual(result['summary']['difficulty_graded'],16)
                    self.assertEqual(result['summary']['rhythms'],{'J':5,'R':6,'S':5})
                    self.assertLessEqual(result['summary']['difficulty_distance'],1,(profile,pool,seed,result['summary']))
                    if profile=='beginner':self.assertGreaterEqual(result['summary']['difficulty_counts'].get(1,0),11)
                    if profile=='ball':self.assertGreaterEqual(result['summary']['difficulty_counts'].get(3,0),5)

    def test_difficulty_check_balance_coverage_and_extras(self):
        dances=[next(d for d in self.cat.dances.values() if d['rscds_grade']==g) for g in (1,2,3,4,None)]
        entries=[Entry(dance_id=d['id']) for d in dances]
        entries+=[Entry(kind='extra',dance_id=dances[-1]['id']),Entry(name='Unidentified')]
        mix=DifficultyMix(one=100,two=0,three=0)
        result=check(ProgrammeRequest(entries=entries,options=Options(difficulty_mix=mix)),self.cat)
        issues={i['code']:i for i in result['issues']}
        self.assertEqual(issues['difficulty_balance']['level'],'warning')
        self.assertEqual(issues['difficulty_ungraded']['indices'],[4])
        self.assertEqual(result['summary']['difficulty_counts'],{1:1,2:1,3:1,4:1})
        self.assertEqual(result['summary']['difficulty_targets'],{1:4,2:0,3:0,4:0})
        self.assertEqual(result['summary']['difficulty_graded'],4)
        self.assertEqual(result['summary']['difficulty_ungraded'],1)
        self.assertIn('4/6',issues['difficulty_coverage']['message'])
        allowed=check(ProgrammeRequest(entries=entries,options=Options(difficulty_mix=mix,allow_ungraded=True)),self.cat)
        self.assertNotIn('difficulty_ungraded',[i['code'] for i in allowed['issues']])
        unlimited=check(ProgrammeRequest(entries=entries),self.cat)
        self.assertFalse(any(i['code'] in ('difficulty_balance','difficulty_ungraded') for i in unlimited['issues']))

    def test_harder_locked_dances_are_balanced_not_rejected(self):
        result=generate(ProgrammeRequest(seed=4),self.cat)
        entries=[Entry(**e) for e in result['entries']]
        # A difficult dance locked late must be counted before filling earlier slots.
        last=entries[-1]
        rhythm=self.cat.dances[last.dance_id]['rhythm']
        d=next(d for d in self.cat.dances.values() if d['rhythm']==rhythm and d['rscds_grade']==3)
        entries[-1]=Entry(dance_id=d['id'],locked=True)
        result=generate(ProgrammeRequest(entries=entries,options=Options(difficulty_mix=DIFFICULTY_PRESETS['beginner']),seed=8),self.cat)
        self.assertEqual(result['entries'][-1]['dance_id'],d['id'])
        self.assertEqual(result['summary']['errors'],0)
        self.assertLessEqual(result['summary']['difficulty_distance'],1)

    def test_ungraded_lock_requires_opt_in_and_never_counts_as_easy(self):
        d=next(d for d in self.cat.dances.values() if d['rhythm']=='J' and d['rscds_grade'] is None)
        entries=[Entry(dance_id=d['id'],locked=True)]
        o=Options(difficulty_mix=DIFFICULTY_PRESETS['beginner'])
        with self.assertRaisesRegex(ValueError,'no published difficulty grade'):
            generate(ProgrammeRequest(entries=entries,options=o),self.cat)
        o.allow_ungraded=True
        result=generate(ProgrammeRequest(entries=entries,options=o,seed=8),self.cat)
        self.assertEqual(result['entries'][0]['dance_id'],d['id'])
        s=result['summary']
        self.assertEqual(s['errors'],0)
        self.assertEqual(sum(s['difficulty_targets'].values()),s['difficulty_graded'])
        self.assertEqual(s['difficulty_graded']+s['difficulty_ungraded'],16)

    def test_all_ungraded_cannot_pass_balance(self):
        d=next(d for d in self.cat.dances.values() if d['rscds_grade'] is None)
        result=check(ProgrammeRequest(entries=[Entry(dance_id=d['id'])],options=Options(difficulty_mix=DifficultyMix(),allow_ungraded=True)),self.cat)
        self.assertIn('difficulty_balance_unknown',[i['code'] for i in result['issues']])

    def test_unavailable_grade_is_a_balance_warning_not_a_ceiling(self):
        cat=deepcopy(self.cat)
        for d in cat.dances.values():d['rscds_grade']=2
        result=generate(ProgrammeRequest(options=Options(difficulty_mix=DIFFICULTY_PRESETS['beginner']),seed=5),cat)
        self.assertEqual(result['summary']['errors'],0)
        self.assertEqual(result['summary']['difficulty_counts'],{2:16})
        self.assertIn('difficulty_balance',[i['code'] for i in result['issues']])

    def test_insufficient_graded_pool_and_no_silent_relaxation(self):
        cat=deepcopy(self.cat)
        for d in cat.dances.values():
            if d['rhythm']=='S':d['rscds_grade']=None
        with self.assertRaisesRegex(ValueError,'Not enough eligible strathspeys'):
            generate(ProgrammeRequest(options=Options(difficulty_mix=DifficultyMix())),cat)
        allowed=generate(ProgrammeRequest(options=Options(difficulty_mix=DifficultyMix(),allow_ungraded=True),seed=11),cat)
        self.assertEqual(allowed['summary']['errors'],0)
        self.assertGreaterEqual(allowed['summary']['difficulty_ungraded'],5)

    def test_difficulty_combines_with_required_figures_and_locks(self):
        o=Options(difficulty_mix=DIFFICULTY_PRESETS['ball'],figure_rules=[FigureRule(key='family:ALLMND',max_count=0,mode='error')])
        result=generate(ProgrammeRequest(options=o,seed=25),self.cat)
        entries=[Entry(**e) for e in result['entries']]
        entries[0].locked=True
        second=generate(ProgrammeRequest(options=o,entries=entries,seed=26),self.cat)
        self.assertEqual(second['entries'][0]['dance_id'],entries[0].dance_id)
        self.assertEqual(second['summary']['errors'],0)
        self.assertLessEqual(second['summary']['difficulty_distance'],1)

    def test_difficulty_option_bounds_and_legacy_drafts(self):
        self.assertIsNone(ProgrammeRequest.model_validate({'options':{'length':16}}).options.difficulty_mix)
        migrated=Options(max_rscds_grade=1,profile='ball')
        self.assertEqual(migrated.difficulty_mix.model_dump(),DIFFICULTY_PRESETS['ball'])
        self.assertIsNone(Options(max_rscds_grade=1,difficulty_mix=None).difficulty_mix)
        for value in (-1,101,1.5):
            with self.assertRaises(ValidationError):DifficultyMix(one=value)
        with self.assertRaisesRegex(ValidationError,'100'):DifficultyMix(one=50,two=50,three=50)
        for n in (0,4,7,16,25,32):
            self.assertEqual(sum(difficulty_targets(DifficultyMix(),n).values()),n)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app=FastAPI();app.include_router(router);cls.client=TestClient(app)

    def test_page_and_search(self):
        self.assertIn('Programme planner',self.client.get('/programmes').text)
        results=self.client.get('/api/programmes/catalogue',params={'q':'machine without horses'}).json()['dances']
        self.assertTrue(results)
        self.assertTrue(any(d['name']=='Machine without Horses, The' for d in results))

    def test_bounds_and_generation_conflict(self):
        for body in [{'options':{'length':100}}, {'options':{'jigs':4}}, {'entries':[{}]*81}]:
            self.assertEqual(self.client.post('/api/programmes/generate',json=body).status_code,422)

    def test_http_generate_then_check(self):
        r=self.client.post('/api/programmes/generate',json={'seed':43})
        self.assertEqual(r.status_code,200)
        result=self.client.post('/api/programmes/check',json={'entries':r.json()['entries']})
        self.assertEqual(result.status_code,200);self.assertEqual(result.json()['summary']['errors'],0)

    def test_http_difficulty_generate_search_and_check(self):
        labels=self.client.get('/api/programmes/catalogue').json()['difficulty_grades']
        self.assertIn('Expert-level',labels['4'])
        body={'options':{'difficulty_mix':DIFFICULTY_PRESETS['ball']},'seed':17}
        response=self.client.post('/api/programmes/generate',json=body)
        self.assertEqual(response.status_code,200)
        self.assertLessEqual(response.json()['summary']['difficulty_distance'],1)
        body['entries']=response.json()['entries']
        checked=self.client.post('/api/programmes/check',json=body).json()
        self.assertEqual(checked['summary']['errors'],0)
        dances=self.client.get('/api/programmes/catalogue',params={'q':'Reel of the 51st Division'}).json()['dances']
        self.assertTrue(any(d['rscds_grade']==1 for d in dances))
        self.assertEqual(self.client.post('/api/programmes/generate',json={'options':{'difficulty_mix':{'one':100,'two':100,'three':0}}}).status_code,422)


if __name__=='__main__':unittest.main()
