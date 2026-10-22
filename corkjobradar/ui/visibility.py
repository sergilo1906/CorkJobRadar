"""Central display decisions. These never grant backend authorization."""
PAGES=('Inicio','Ofertas de empleo','Mis candidaturas','AutoApply','Actividad y notificaciones','Perfil y configuración')
APPLICATION_STATES=('Pendientes de preparar','Preparadas','Requieren intervención','Enviadas declaradas manualmente','Enviadas con confirmación externa','Estado incierto','Rechazadas o cerradas')


def runtime_actions(control,alive=True):
    if control['state'] in {'STOPPING','PAUSING'}:return ()
    if control['desired']=='RUNNING':return ('PAUSE','STOP')
    if control['desired']=='PAUSED':return ('RESUME','STOP')
    return ('START',)


def application_state(*,closed=False,manual=False,confirmed=False,uncertain=False,intervention=False,prepared=False,needs_review=False):
    # Uncertainty and proven submissions must never offer another application.
    if uncertain:return APPLICATION_STATES[5]
    if closed:return APPLICATION_STATES[6]
    if confirmed:return APPLICATION_STATES[4]
    if manual:return APPLICATION_STATES[3]
    if intervention:return APPLICATION_STATES[2]
    if prepared:return APPLICATION_STATES[1]
    return APPLICATION_STATES[2] if needs_review else APPLICATION_STATES[0]


def actions_for(*,cv_approved,preparation_allowed,application,channel_validated=False,policy_authorized=False,live_released=False):
    submitted=application in APPLICATION_STATES[3:]
    return {'prepare':bool(cv_approved and preparation_allowed and not submitted),
            'review_cv':not cv_approved,'register':application==APPLICATION_STATES[1],
            'evidence':application==APPLICATION_STATES[3],
            'open_application':not submitted,
            'send':bool(live_released and channel_validated and policy_authorized and cv_approved and preparation_allowed and not submitted)}


def safe_controls(control,action):
    if action not in runtime_actions(control) and action!='SEARCH_NOW':raise ValueError('ACTION_NOT_AVAILABLE_FOR_CURRENT_STATE')
    if action=='SEARCH_NOW' and (control['state'] in {'STOPPING','PAUSING'} or control.get('active_kind')):raise ValueError('WORK_ALREADY_ACTIVE')
