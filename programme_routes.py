"""Programme planner HTTP routes; catalogue reads only, no shared draft storage."""
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from programme_planner import ProgrammeRequest, ImportRequest, DIFFICULTY_PRESETS, catalogue, check, generate, import_programme
from dance_difficulty import GRADE_LABELS

router=APIRouter()
templates=Jinja2Templates(directory='templates')


@router.get('/programmes')
def programme_page(request: Request):
    return templates.TemplateResponse(request=request,name='programmes.html',context={})


@router.get('/api/programmes/catalogue')
def planner_catalogue(q: str = Query(default='',max_length=200)):
    cat=catalogue()
    return {'dances':cat.search(q), 'figures':cat.figure_choices if not q else [],
            'difficulty_grades':GRADE_LABELS if not q else {},
            'difficulty_presets':DIFFICULTY_PRESETS if not q else {},
            'catalogue_size':len(cat.dances),'sample_size':sum(d['occurrences']>0 for d in cat.dances.values())}


@router.post('/api/programmes/check')
def check_programme(data: ProgrammeRequest):
    return check(data,catalogue())


@router.post('/api/programmes/generate')
def generate_programme(data: ProgrammeRequest):
    try:return generate(data,catalogue())
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post('/api/programmes/import')
def parse_programme(data: ImportRequest):
    try:return {'entries':import_programme(data.text,catalogue())}
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
