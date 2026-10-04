"""Catalogue-backed programme generation and checking, independent of chat/LLMs.

The catalogue is read-only. Unknown metadata is never presented as a passed rule.
Generation is a bounded search; explicit constraints are never silently relaxed.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from dance_difficulty import with_difficulty

ROOT = Path(__file__).resolve().parent
Mode = Literal['error', 'warning', 'off']
FAMILY_NAMES = {'REEL':'Reels', 'HR':'Hands round', 'HX':'Hands across', 'FIG8':'Figures of eight',
    'ALLMND':'Allemande', 'POUSS':'Poussette', 'SETLNK':'Set and link', 'SETLIN':'Setting in lines',
    'KNOT':'Knot / slipknot', 'ESPAN':'Espagnole', 'R&L':'Rights and lefts', 'GCHAIN':'Grand chain',
    'CPCP':'Corners pass and turn', 'PET':'Petronella', 'DBLTRI':'Double triangles'}


def normalise(name):
    text = unicodedata.normalize('NFKD', name.casefold()).replace('&', 'and')
    text = re.sub(r'[^a-z0-9 ]', '', text)
    return re.sub(r'^(the|a|an) | (the|a|an)$', '', ' '.join(text.split()))


class Entry(BaseModel):
    kind: Literal['dance', 'break', 'extra'] = 'dance'
    dance_id: int | None = Field(default=None, ge=1)
    name: str = Field(default='', max_length=300)
    locked: bool = False


class FigureRule(BaseModel):
    key: str = Field(max_length=80)
    max_count: int | None = Field(default=None, ge=0, le=32)
    min_gap: int = Field(default=0, ge=0, le=16)
    mode: Mode = 'warning'


DIFFICULTY_PRESETS = {
    'beginner': {'one': 75, 'two': 25, 'three': 0, 'expert': 0},
    'social': {'one': 40, 'two': 45, 'three': 15, 'expert': 0},
    'ball': {'one': 20, 'two': 45, 'three': 35, 'expert': 0},
}


class DifficultyMix(BaseModel):
    one: int = Field(default=40, ge=0, le=100)
    two: int = Field(default=45, ge=0, le=100)
    three: int = Field(default=15, ge=0, le=100)
    expert: int = Field(default=0, ge=0, le=100)

    @model_validator(mode='after')
    def valid_total(self):
        if sum(self.model_dump().values()) != 100:
            raise ValueError('Difficulty percentages must add up to 100.')
        return self

    def shares(self):
        return dict(zip((1,2,3,4), (self.one,self.two,self.three,self.expert)))


def difficulty_targets(mix, count):
    """Round shares to whole dances, preserving the total with largest remainders."""
    if mix is None:return {}
    raw={grade: count*share for grade,share in mix.shares().items()}
    result={grade: value//100 for grade,value in raw.items()}
    for grade in sorted(raw,key=lambda g: (-(raw[g]%100),g))[:count-sum(result.values())]:
        result[grade]+=1
    return result


class Options(BaseModel):
    length: int = Field(default=16, ge=4, le=32)
    jigs: int = Field(default=5, ge=0, le=32)
    reels: int = Field(default=6, ge=0, le=32)
    strathspeys: int = Field(default=5, ge=0, le=32)
    break_after: int = Field(default=8, ge=0, le=31)
    profile: Literal['social', 'ball', 'beginner'] = 'social'
    rhythm_mode: Mode = 'error'
    duplicate_mode: Mode = 'error'
    max_fast_run: int = Field(default=2, ge=0, le=32)
    rscds_target: int | None = Field(default=75, ge=0, le=100)
    rscds_tolerance: int = Field(default=15, ge=0, le=100)
    jig_opener: bool = True
    quick_finish: bool = True
    pool: Literal['sample', 'catalogue'] = 'sample'
    difficulty_mix: DifficultyMix | None = None
    allow_ungraded: bool = False
    figure_rules: list[FigureRule] = Field(default_factory=list, max_length=20)

    @model_validator(mode='before')
    @classmethod
    def migrate_difficulty_limit(cls, data):
        # Old drafts retain their other settings; replace the former cap with
        # the event's suggested balance rather than retaining a hidden ceiling.
        if isinstance(data,dict) and 'difficulty_mix' not in data and data.get('max_rscds_grade') is not None:
            data={**data,'difficulty_mix':DIFFICULTY_PRESETS.get(data.get('profile','social'),DIFFICULTY_PRESETS['social'])}
        return data


class ProgrammeRequest(BaseModel):
    entries: list[Entry] = Field(default_factory=list, max_length=80)
    options: Options = Field(default_factory=Options)
    seed: int | None = None


class ImportRequest(BaseModel):
    text: str = Field(max_length=20000)


class Catalogue:
    def __init__(self, path=None):
        db = Path(path or os.environ.get('SCDDB_SQLITE', ROOT/'data/scddb/scddb.sqlite')).resolve()
        con = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        self.dances = {}
        for row in con.execute('''SELECT d.id,d.name,t.short_name rhythm,d.barsperrepeat bars,
             d.formations_verified,d.rscds_grade,s.name set_shape,c.name couples FROM dance d
             LEFT JOIN dancetype t ON t.id=d.type_id LEFT JOIN shape s ON s.id=d.shape_id
             LEFT JOIN couples c ON c.id=d.couples_id'''):
            d = with_difficulty(dict(row))
            d.update(formations=[], families=[], publications=[], rscds=None, occurrences=0)
            self.dances[d['id']] = d
        self.figures = {}
        for row in con.execute('SELECT id,name,searchid FROM formation'):
            f = dict(row)
            self.figures[f['id']] = f
        for row in con.execute('SELECT dance_id,formation_id FROM dancesformationsmap'):
            if row['dance_id'] in self.dances and row['formation_id'] in self.figures:
                d=self.dances[row['dance_id']];f=self.figures[row['formation_id']]
                d['formations'].append(f['id'])
                if f['searchid']:d['families'].append(f['searchid'].split(';')[0].strip())
        for row in con.execute('''SELECT m.dance_id,p.name,p.rscds FROM dancespublicationsmap m
                                  JOIN publication p ON p.id=m.publication_id'''):
            if row['dance_id'] in self.dances:
                self.dances[row['dance_id']]['publications'].append({'name':row['name'],'rscds':bool(row['rscds'])})
        self.names = defaultdict(set)
        for d in self.dances.values():
            d['families']=sorted(set(d['families']))
            d['formations']=sorted(set(d['formations']))
            if d['publications']:d['rscds']=any(p['rscds'] for p in d['publications'])
            self.names[normalise(d['name'])].add(d['id'])
        for row in con.execute('SELECT dance_id,name FROM dancealias'):
            if row['dance_id'] in self.dances:self.names[normalise(row['name'])].add(row['dance_id'])
        con.close()
        seed_path = ROOT/'assets/programme-sample.json'
        if seed_path.exists():
            for key,count in json.loads(seed_path.read_text())['dance_occurrences'].items():
                if int(key) in self.dances:self.dances[int(key)]['occurrences']=count
        roots=sorted({f for d in self.dances.values() for f in d['families']})
        self.family_names = {root:FAMILY_NAMES.get(root, next((f['name'] for f in self.figures.values()
            if f['searchid'].split(';')[0].strip()==root),root)) for root in roots}
        self.figure_choices = [{'key':'family:'+f,'name':self.family_names[f]+' (family)'} for f in roots]
        self.figure_choices += [{'key':'id:'+str(f['id']),'name':f['name']+' (exact)'} for f in self.figures.values()]
        self.figure_labels = {f['key']:f['name'] for f in self.figure_choices}

    def public(self, dance):
        if not dance:return None
        return {**dance, 'figure_names':[self.figures[i]['name'] for i in dance['formations']],
                'url':f"https://my.strathspey.org/dd/dance/{dance['id']}/"}

    def search(self, query, limit=20):
        query=normalise(query)
        if not query:return []
        exact=self.names.get(query,set())
        alias_ids={i for n,ids in self.names.items() if query in n for i in ids}
        found=[self.dances[i] for i in alias_ids]
        found.sort(key=lambda d:(d['id'] not in exact, not normalise(d['name']).startswith(query), -d['occurrences'],d['name']))
        return [self.public(d) for d in found[:limit]]

    def has_figure(self, d, key):
        if key.startswith('family:'):return key[7:] in d['families']
        if key.startswith('id:') and key[3:].isdigit():return int(key[3:]) in d['formations']
        return False


@lru_cache(maxsize=1)
def catalogue():return Catalogue()


def import_programme(text, cat):
    entries=[]
    extra=False
    for raw in re.split(r'[\n;]+',text):
        name=re.sub(r'^\s*(?:\d+[.)\s]+|[-•]\s*)','',raw).strip()
        if not name:continue
        if re.fullmatch(r'\W*(main programme|main dances|programme)\W*',name,re.I):extra=False;continue
        if re.fullmatch(r'\W*(extras?|reserves?)\W*',name,re.I):extra=True;continue
        if re.fullmatch(r'\W*(interval|break|supper|intermission|refreshments|pause)(?:\s*\([^)]*\))?\W*',name,re.I):
            entries.append(Entry(kind='break',name=name));continue
        link=re.search(r'https?://(?:my\.)?strathspey\.org/dd/dance/(\d+)',name)
        ids={int(link[1])} if link and int(link[1]) in cat.dances else cat.names.get(normalise(name),set())
        # Only remove explicit trailing format notation; do not guess ambiguous names.
        if not ids:
            clean=re.sub(r'\s*[\[(]?\s*[JRS]\s*\d+(?:\s+\d[^\n]*)?[\])]?\s*$','',name,flags=re.I).strip()
            ids=cat.names.get(normalise(clean),set())
        entries.append(Entry(kind='extra' if extra else 'dance',name=name,dance_id=next(iter(ids)) if len(ids)==1 else None))
    if len(entries)>80:raise ValueError('Please import at most 80 programme items at a time.')
    return enrich(entries,cat)


def enrich(entries,cat):
    return [{**e.model_dump(), 'dance':cat.public(cat.dances.get(e.dance_id)),
             'candidates':cat.search(e.name,6) if e.kind!='break' and e.dance_id not in cat.dances else []} for e in entries]


def check(req,cat):
    options=req.options;entries=req.entries
    issues=[]
    def add(code,level,message,indices=()):
        if level!='off':issues.append({'code':code,'level':level,'message':message,'indices':list(indices)})
    main=[(i,e,cat.dances.get(e.dance_id)) for i,e in enumerate(entries) if e.kind=='dance']
    known=[d for _,_,d in main if d]
    for i,e in enumerate(entries):
        if e.kind!='break' and e.dance_id not in cat.dances:
            add('unresolved','error',f'Identify “{e.name or "Unnamed dance"}” to check it reliably.',[i])
    if len(main)!=options.length:add('length','warning',f'{len(main)} main dances; your target is {options.length}.')
    counts=Counter(d['rhythm'] for d in known)
    desired={'J':options.jigs,'R':options.reels,'S':options.strathspeys}
    if sum(desired.values())!=options.length:add('rhythm_total','error','Jig, reel and strathspey targets must add up to the programme length.')
    elif any(counts[r]!=n for r,n in desired.items()):add('rhythm_mix','warning',f"Target J/R/S: {options.jigs}/{options.reels}/{options.strathspeys}; identified: {counts['J']}/{counts['R']}/{counts['S']}.")
    seen=defaultdict(list)
    for i,e,d in main:
        if d:seen[d['id']].append(i)
    for id,indices in seen.items():
        if len(indices)>1:add('duplicate',options.duplicate_mode,f"{cat.dances[id]['name']} appears {len(indices)} times in the main programme.",indices)
    run=[];max_run=0;eligible=0
    for i,e in enumerate(entries):
        d=cat.dances.get(e.dance_id) if e.kind=='dance' else None
        if d and d['rhythm'] in ('J','R'):run.append(i);max_run=max(max_run,len(run))
        else:
            if options.max_fast_run and len(run)>options.max_fast_run:add('fast_run','warning',f'{len(run)} quick-time dances in a row (limit {options.max_fast_run}).',run)
            run=[]
        if i and d and e.kind==entries[i-1].kind=='dance':
            prev=cat.dances.get(entries[i-1].dance_id)
            if prev and prev['rhythm'] in ('J','R','S') and d['rhythm'] in ('J','R','S'):
                eligible+=1
                if prev['rhythm']==d['rhythm']:add('rhythm_neighbours',options.rhythm_mode,f"Two { {'J':'jigs','R':'reels','S':'strathspeys'}[d['rhythm']]} next to each other: {prev['name']} → {d['name']}.",[i-1,i])
    if options.max_fast_run and len(run)>options.max_fast_run:add('fast_run','warning',f'{len(run)} quick-time dances in a row (limit {options.max_fast_run}).',run)
    tagged=sum(bool(d['formations']) for d in known);verified=sum(d['formations_verified']==1 for d in known)
    if tagged<len(main) or verified<tagged:add('formation_coverage','info',f'Figure data: {tagged}/{len(main)} dances tagged; {verified} verified. Missing or unverified tags cannot certify a figure rule.')
    for rule in options.figure_rules:
        if rule.key not in cat.figure_labels:add('unknown_figure','error','A selected figure rule is no longer available. Remove it and choose the figure again.');continue
        if rule.mode=='off':continue
        if rule.mode=='error' and (tagged<len(main) or verified<len(main)):
            add('figure_unverified','error','A required figure rule cannot be confirmed: every main dance needs verified figure data. Use a warning or choose dances with verified tags.')
        hits=[i for i,e,d in main if d and cat.has_figure(d,rule.key)]
        label=cat.figure_labels[rule.key]
        if rule.max_count is not None and len(hits)>rule.max_count:add('figure_count',rule.mode,f'{label}: {len(hits)} dances, exceeding your limit of {rule.max_count}.',hits)
        last=None;gap=0
        for i,e in enumerate(entries):
            if e.kind!='dance' or e.dance_id not in cat.dances:last=None;gap=0;continue
            if i in hits:
                if last is not None and gap<rule.min_gap:add('figure_gap',rule.mode,f'{label}: {gap} intervening dances; you asked for at least {rule.min_gap}.',[last,i])
                last=i;gap=0
            elif last is not None:gap+=1
    pubs=[d for d in known if d['rscds'] is not None];rs=sum(d['rscds'] for d in pubs)
    share=round(rs/len(pubs)*100,1) if pubs else None
    if options.rscds_target is not None and share is not None and abs(share-options.rscds_target)>options.rscds_tolerance:
        add('rscds_mix','warning',f'{share}% RSCDS-published among dances with publication data; target {options.rscds_target}% ± {options.rscds_tolerance}%.')
    if len(pubs)<len(main):add('publication_coverage','info',f'Publication status is known for {len(pubs)}/{len(main)} main dances.')
    if any(d['rhythm'] not in ('J','R','S') for d in known):add('mixed_rhythm','info','Medleys, alternative and unknown rhythms are retained, but not assessed as pure J/R/S neighbours.')
    if main and main[0][2] and options.jig_opener and main[0][2]['rhythm']!='J':add('opener','warning','Your opening preference is a jig.',[main[0][0]])
    if main and main[-1][2] and options.quick_finish and main[-1][2]['rhythm'] not in ('J','R'):add('finale','warning','Your closing preference is a jig or reel.',[main[-1][0]])
    graded=[d for d in known if d['rscds_grade'] is not None]
    grade_counts=Counter(d['rscds_grade'] for d in graded)
    ungraded=[i for i,e,d in main if d and d['rscds_grade'] is None]
    grade_targets=difficulty_targets(options.difficulty_mix,len(graded))
    difficulty_distance=sum(abs(grade_counts[g]-n) for g,n in grade_targets.items())/2
    if options.difficulty_mix is not None:
        if difficulty_distance>1:
            add('difficulty_balance','warning',
                'Difficulty balance differs from your target by more than one dance. Compare the actual and target counts below.')
        if ungraded and not options.allow_ungraded:
            add('difficulty_ungraded','error',
                f'{len(ungraded)} main dance(s) have no published difficulty grade. Choose graded dances or allow ungraded dances explicitly.',ungraded)
        if not graded and main:
            add('difficulty_balance_unknown','warning','No main dances have published grades, so the difficulty balance cannot be assessed.')
    if len(graded)<len(main):
        add('difficulty_coverage','info',f'Published difficulty grades: {len(graded)}/{len(main)} main dances. Ungraded or unidentified dances have not been assessed for difficulty.',ungraded)
    families=Counter(f for d in known for f in d['families'])
    return {'entries':enrich(entries,cat),'issues':issues,'summary':{
        'main_count':len(main),'extras':sum(e.kind=='extra' for e in entries),'resolved':len(known),
        'rhythms':dict(counts),'rscds_share':share,'publication_known':len(pubs),'formation_tagged':tagged,
        'formation_verified':verified,'max_fast_run':max_run,'eligible_rhythm_pairs':eligible,
        'errors':sum(i['level']=='error' for i in issues),'warnings':sum(i['level']=='warning' for i in issues),
        'families':[{'key':'family:'+f,'name':cat.family_names.get(f,f),'count':n} for f,n in families.most_common()],
        'difficulty_graded':len(graded),'difficulty_ungraded':len(ungraded),
        'difficulty_counts':dict(grade_counts),
        'difficulty_targets':grade_targets,'difficulty_distance':difficulty_distance,
        'difficulty_status':f'{len(graded)}/{len(main)} main dances have published RSCDS grades via SCDDB. No difficulty is inferred for ungraded dances.',
        'music_status':'Musical style is not assessed.'}}


def generate(req,cat):
    """Search rhythm orders with fixed slots, then improve soft constraints over attempts."""
    o=req.options
    target={'J':o.jigs,'R':o.reels,'S':o.strathspeys}
    if sum(target.values())!=o.length:raise ValueError('The jig, reel and strathspey counts must add up to the programme length.')
    if o.break_after>=o.length:raise ValueError('Place the interval before the final dance, or set it to 0 for no interval.')
    for rule in o.figure_rules:
        if rule.key not in cat.figure_labels:raise ValueError('Choose a valid figure for every figure rule.')
    mains=[e for e in req.entries if e.kind=='dance']
    locks={i:e for i,e in enumerate(mains) if e.locked}
    if any(i>=o.length for i in locks):raise ValueError('A locked dance is beyond the requested length. Increase the length or unlock it.')
    for e in locks.values():
        if e.dance_id not in cat.dances:raise ValueError('Identify every locked dance before generating.')
        if cat.dances[e.dance_id]['rhythm'] not in target:raise ValueError('This generator fills J/R/S slots. Keep mixed-rhythm dances in the checker, or unlock them before generating.')
    lock_ids=[e.dance_id for e in locks.values()]
    if o.duplicate_mode=='error' and len(lock_ids)!=len(set(lock_ids)):raise ValueError('The locked positions repeat a dance, but your duplicate rule forbids repeats.')
    remaining=Counter(target)
    for e in locks.values():remaining[cat.dances[e.dance_id]['rhythm']]-=1
    if min(remaining.values())<0:raise ValueError('The locked dances exceed one of your rhythm counts. Change the counts or unlock a dance.')
    # Preserve explicitly placed intervals and extras while regenerating the main dances.
    breaks=defaultdict(list);pos=0
    for e in req.entries:
        if e.kind=='dance':pos+=1
        elif e.kind=='break':breaks[pos].append(e)
    if any(p>=o.length for p in breaks):raise ValueError('An existing interval is beyond the new programme length. Move or remove it first.')
    if not breaks and o.break_after:breaks[o.break_after]=[Entry(kind='break',name='Interval')]
    extras=[e for e in req.entries if e.kind=='extra']
    pool=[d for d in cat.dances.values() if d['rhythm'] in target and (o.pool=='catalogue' or d['occurrences']>0)]
    if not pool:raise ValueError('No dances available in the chosen pool.')
    hard_figures=[r for r in o.figure_rules if r.mode=='error']
    if hard_figures:
        # A hard figure constraint requires verified metadata, not an assumed absence.
        pool=[d for d in pool if d['formations'] and d['formations_verified']==1]
        if any(not cat.dances[e.dance_id]['formations'] or cat.dances[e.dance_id]['formations_verified']!=1 for e in locks.values()):
            raise ValueError('A locked dance has unverified figure data. Use a warning instead of a required figure rule, or unlock it.')
    if o.difficulty_mix is not None and not o.allow_ungraded:
        for e in locks.values():
            d=cat.dances[e.dance_id]
            if d['rscds_grade'] is None:
                raise ValueError(f'Locked dance “{d["name"]}” has no published difficulty grade. Allow ungraded dances or unlock it.')
        pool=[d for d in pool if d['rscds_grade'] is not None]
    by_rhythm={r:[d for d in pool if d['rhythm']==r] for r in target}
    by_grade={r:{g:[d for d in by_rhythm[r] if d['rscds_grade']==g] for g in (1,2,3,4,None)} for r in target}
    for rhythm,needed in remaining.items():
        available=sum(d['id'] not in lock_ids for d in by_rhythm[rhythm])
        if needed and (available==0 or (o.duplicate_mode=='error' and available<needed)):
            raise ValueError(f'Not enough eligible { {"J":"jigs","R":"reels","S":"strathspeys"}[rhythm]} in the chosen pool for these requirements. Try the wider catalogue, adjust your difficulty or figure settings, or reduce that rhythm count.')
    seed=req.seed if req.seed is not None else random.SystemRandom().randrange(2**32)
    rng=random.Random(seed)
    best=None;best_score=float('inf')
    # Memoised rhythm feasibility prevents misleading "can't find" for simple count conflicts.
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def feasible(pos,j,r,s,prev):
        if pos==o.length:return j==r==s==0
        counts={'J':j,'R':r,'S':s}
        choices=[cat.dances[locks[pos].dance_id]['rhythm']] if pos in locks else list(target)
        for rhythm in choices:
            if counts[rhythm]<=0:continue
            if o.rhythm_mode=='error' and pos not in breaks and rhythm==prev:continue
            nxt=counts.copy();nxt[rhythm]-=1
            if feasible(pos+1,nxt['J'],nxt['R'],nxt['S'],rhythm):return True
        return False
    if not feasible(0,o.jigs,o.reels,o.strathspeys,''):
        raise ValueError('Those rhythm counts and locked positions cannot avoid neighbouring repeats. Adjust the counts, interval, locks or rhythm rule.')
    for attempt in range(60):
        chosen=[];used=set();counts=Counter(target);figure_counts=Counter();last_figure={};section_start=0;failed=False
        # Reserve all locked grades before filling free slots, including later locks.
        grade_counts=Counter(cat.dances[e.dance_id]['rscds_grade'] for e in locks.values() if cat.dances[e.dance_id]['rscds_grade'] is not None)
        for pos in range(o.length):
            if pos in breaks:section_start=pos;last_figure={}
            previous=chosen[-1]['rhythm'] if chosen and pos not in breaks else ''
            choices=[cat.dances[locks[pos].dance_id]] if pos in locks else []
            if pos not in locks:
                for rhythm in target:
                    if counts[rhythm]<=0:continue
                    nxt=counts.copy();nxt[rhythm]-=1
                    if o.rhythm_mode=='error' and rhythm==previous:continue
                    if not feasible(pos+1,nxt['J'],nxt['R'],nxt['S'],rhythm):continue
                    groups=by_grade[rhythm].values() if o.difficulty_mix else [by_rhythm[rhythm]]
                    for candidates in groups:
                        choices.extend(rng.sample(candidates,min(len(candidates),40 if o.difficulty_mix else 100)))
            ranked=[]
            for d in choices:
                rhythm=d['rhythm']
                if counts[rhythm]<=0:continue
                if o.duplicate_mode=='error' and d['id'] in used:continue
                if pos not in locks and d['id'] in lock_ids:continue
                if o.rhythm_mode=='error' and rhythm==previous:continue
                hits=[r for r in o.figure_rules if r.mode!='off' and cat.has_figure(d,r.key)]
                if any(r.mode=='error' and ((r.max_count is not None and figure_counts[r.key]>=r.max_count) or (r.key in last_figure and pos-last_figure[r.key]-1<r.min_gap)) for r in hits):continue
                score=rng.random()*2 - math.log1p(d['occurrences'])*.22
                if o.difficulty_mix is not None and pos not in locks:
                    grade=d['rscds_grade']
                    if grade is None:
                        # Unknowns may meet other preferences, but never count as easy.
                        score+=2
                    else:
                        n=sum(grade_counts.values())
                        shares=o.difficulty_mix.shares()
                        before=sum((grade_counts[g]-n*shares[g]/100)**2 for g in shares)
                        after=sum((grade_counts[g]+int(g==grade)-(n+1)*shares[g]/100)**2 for g in shares)
                        score+=6*(after-before)
                if not d['formations']:score+=1
                if pos==0 and o.jig_opener and rhythm!='J':score+=4
                if pos==o.length-1 and o.quick_finish and rhythm not in ('J','R'):score+=4
                if rhythm==previous and o.rhythm_mode!='off':score+=6
                if o.max_fast_run and rhythm in ('J','R'):
                    run=1
                    for old in reversed(chosen[section_start:]):
                        if old['rhythm'] not in ('J','R'):break
                        run+=1
                    if run>o.max_fast_run:score+=8
                if o.rscds_target is not None:
                    known=[x for x in chosen if x['rscds'] is not None]
                    desired=(len(known)+1)*o.rscds_target/100
                    actual=sum(x['rscds'] for x in known)
                    if d['rscds'] is None:score+=2
                    else:score+=abs(actual+int(d['rscds'])-desired)*3
                for rule in hits:
                    if rule.max_count is not None and figure_counts[rule.key]>=rule.max_count:score+=10
                    if rule.key in last_figure and pos-last_figure[rule.key]-1<rule.min_gap:score+=10
                ranked.append((score,rng.random(),d))
            if not ranked:failed=True;break
            d=min(ranked,key=lambda x:(x[0],x[1]))[2]
            chosen.append(d);used.add(d['id']);counts[d['rhythm']]-=1
            if pos not in locks and d['rscds_grade'] is not None:grade_counts[d['rscds_grade']]+=1
            for rule in o.figure_rules:
                if cat.has_figure(d,rule.key):figure_counts[rule.key]+=1;last_figure[rule.key]=pos
        if failed:continue
        entries=[]
        for i,d in enumerate(chosen):
            entries.extend(breaks.get(i,[]))
            entries.append(Entry(dance_id=d['id'],name=d['name'],locked=i in locks))
        entries.extend(extras)
        result=check(ProgrammeRequest(entries=entries,options=o),cat)
        if any(x['level']=='error' for x in result['issues']):continue
        score=6*result['summary']['difficulty_distance']+sum(5 if x['code'].startswith('figure_') else 1 for x in result['issues'] if x['level']=='warning')
        if score<best_score:best_score=score;best=result
        if score==0:break
    if best is None:raise ValueError('No programme was found within the search budget. Your requirements were kept intact. Try a wider dance pool, fewer locks, or less restrictive figure rules; this does not prove there is no solution.')
    best['seed']=seed
    best['generation_note']='Your locked dances and required rules were preserved. Remaining suggestions are shown in the check.'
    return best
