def score(facts, cat, scope, profile, commute_verified=False):
    sector='IT' if cat=='IT' else 'NO_IT'
    w = profile.get('weights_by_sector',{}).get(sector,profile['weights'])
    def val(key):
        return facts[key]['value']
    exp = val('experience')
    schedule = val('schedule') or {}
    contract = val('contract')
    sal = val('salary')
    values = {
        'experience': (1 if exp is not None and exp <= 3 else .2 if exp is not None else .5),
        'schedule': .5,
        'commute': 1 if commute_verified else 0 if scope == 'FUERA_DE_ALCANCE' else .5,
        'stability': 1 if contract == 'permanent' else .4 if contract else .5,
        'salary': .5,
        'learning': 1 if val('learning') else .5,
        'functions': 1 if cat == 'IT' else .8 if cat in {'Produccion','Almacen','Tecnicos'} else .5,
    }
    if schedule:
        values['schedule'] = .8
        if cat != 'IT':
            values['schedule'] = 1 if 'lunes_viernes' in schedule else .5
            if any(k in schedule for k in ('noches','rotacion','fines_semana')):
                values['schedule'] = .2
        elif any(k in schedule for k in ('noches','rotacion','guardias')):
            values['schedule'] = .5
    if sal:
        target = 30000 if sal['unit'] == 'año' and cat == 'IT' else 15 if sal['unit'] == 'hora' else None
        if target:
            values['salary'] = min(1,sal['min']/target)
    allowed_windows = profile.get('accepted_time_windows',[])
    if allowed_windows and any(key in schedule and key not in allowed_windows for key in ('noches','rotacion','guardias','fines_semana')):
        values['schedule'] = .2
    known={'experience':exp is not None,'schedule':bool(schedule),'commute':commute_verified or scope=='FUERA_DE_ALCANCE',
           'stability':contract is not None,'salary':sal is not None,'learning':val('learning') is not None,'functions':False}
    reasons={
        'experience':f'Experiencia publicada: {exp} años; preferencia por entrada/junior hasta 3 años' if exp is not None else 'Experiencia imprescindible desconocida; valor neutral provisional',
        'schedule':f'Horario publicado: {schedule}. Regla de preferencias para {sector}; IT sin penalización automática de fin de semana' if schedule else 'Horario desconocido; valor neutral provisional',
        'commute':'Ruta de ida/vuelta documentada o remoto Irlanda' if commute_verified else 'Fuera del alcance establecido' if scope=='FUERA_DE_ALCANCE' else 'Trayecto real sin coche pendiente; valor neutral provisional',
        'stability':f'Contrato publicado: {contract}' if contract else 'Contrato desconocido; valor neutral provisional',
        'salary':f"Salario publicado: {sal['min']} EUR/{sal['unit']}; comparación orientativa sin anualizar" if sal else 'Salario desconocido; valor neutral provisional',
        'learning':'Formación mencionada; revisar alcance en la cita' if val('learning') else 'Formación empresarial no acreditada',
        'functions':f'Prioridad orientativa del sector {cat}; no acredita requisitos cumplidos'}
    explanation = [{'criterion':k,'points':round(values[k]*w[k],1),'max':w[k],
                    'evidence_known':known[k],'minimum_points':round(values[k]*w[k],1) if known[k] else 0,
                    'maximum_points':round(values[k]*w[k],1) if known[k] else w[k],
                    'reason':reasons[k]} for k in w]
    return round(sum(row['points'] for row in explanation)), explanation
