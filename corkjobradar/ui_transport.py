import json
from datetime import datetime,timedelta
import streamlit as st
from .config import now
from .transit import Transit,ATTRIBUTION,TRANSIT_PATH


def assisted_transport(db,job_id,profile,launch):
    st.subheader('Autobús directo: horarios oficiales y confirmación de accesos')
    st.caption(ATTRIBUTION)
    st.link_button('Fuente y condiciones NTA','https://developer.nationaltransport.ie/usagepolicy')
    st.link_button('Consultar TFI para caminar, bicicleta y avisos','https://www.transportforireland.ie/plan-a-journey/')
    if st.button('Actualizar e importar horarios Bus Éireann'):
        launch('transit_refresh')
    if not TRANSIT_PATH.exists():
        st.write('Importa los horarios o usa la comprobación manual de abajo.')
        return
    try:
        transit=Transit();feed=transit.latest();metadata=json.loads(feed['metadata'])
        st.write('Horario importado: '+feed['imported_at'])
        st.caption('Paradas del área Cork (51,7–52,1 N; 8,9–8,0 O). Solo este operador. Cuatro paradas separadas: el sentido de vuelta puede usar otra acera.')
        with st.expander('Vigencia y procedencia del horario'):
            st.json(metadata)
        stops=transit.stops();options={s['id']:s for s in stops}
        with st.form('scheduled_bus'):
            selected=[]
            for key,label in [('origin_out','Ida: parada cerca de Ballinlough'),('destination_out','Ida: parada cerca del trabajo'),
                              ('origin_back','Vuelta: parada cerca del trabajo'),('destination_back','Vuelta: parada cerca de Ballinlough')]:
                selected.append(st.selectbox(label,list(options),index=None,
                    format_func=lambda i:f"{options[i]['name']} · {i}",key=key))
            day=st.date_input('Día concreto que comprobar',key='bus_day')
            start=st.time_input('Entrada publicada o confirmada',value=None,key='shift_start')
            end=st.time_input('Salida publicada o confirmada',value=None,key='shift_end')
            overnight=st.checkbox('La salida es al día siguiente')
            origin_walk=st.number_input('Minutos a pie comprobados desde tu origen a la parada',min_value=0,value=None,step=1)
            destination_walk=st.number_input('Minutos a pie comprobados entre parada y trabajo',min_value=0,value=None,step=1)
            work_return_walk=st.number_input('Vuelta: minutos del trabajo a la parada de regreso',min_value=0,value=None,step=1)
            home_return_walk=st.number_input('Vuelta: minutos de la parada de regreso al origen',min_value=0,value=None,step=1)
            extra_days=st.multiselect('Otras fechas con este mismo turno que deben comprobarse',
                                     [day+timedelta(days=i) for i in range(1,15)])
            maximum=st.number_input('Máximo por trayecto completo en minutos (opcional)',min_value=1,value=None,step=1)
            buffer=st.number_input('Margen antes de entrar, en minutos (tu preferencia)',min_value=0,value=10,step=1)
            if st.form_submit_button('Calcular ida y vuelta sin transbordos'):
                if not all(selected) or start is None or end is None or any(v is None for v in (origin_walk,destination_walk,work_return_walk,home_return_walk)):
                    st.error('Selecciona las cuatro paradas, el turno y los accesos comprobados. No se supondrán tiempos a pie.')
                else:
                    try:
                        start_at=datetime.combine(day,start);end_at=datetime.combine(day,end)+timedelta(days=int(overnight))
                        plan=transit.shift_plan(*selected,start_at,end_at,origin_walk,destination_walk,buffer,
                                                walk_work_return=work_return_walk,walk_home_return=home_return_walk)
                        shifts=[{'start':datetime.combine(d,start).isoformat(),'end':(datetime.combine(d,end)+timedelta(days=int(overnight))).isoformat()} for d in [day]+extra_days]
                        plan['schedule_check']=transit.shift_schedule(*selected,shifts,
                            {'home_to_out_stop':origin_walk,'out_stop_to_work':destination_walk,'work_to_back_stop':work_return_walk,'back_stop_to_home':home_return_walk},buffer=buffer,max_minutes=maximum)
                        plan['job_id']=job_id
                        st.session_state['bus_plan']=plan
                        db.event('TRANSIT_PLAN',plan,job_id=job_id)
                    except Exception as exc:
                        st.error(str(exc))
        plan=st.session_state.get('bus_plan')
        if plan and plan.get('job_id')==job_id:
            st.write(plan['status'])
            st.write(f"Idas compatibles: {plan['outbound_count']} · Vueltas compatibles: {plan['return_count']}")
            st.dataframe(plan['outbound'],hide_index=True,width='stretch')
            st.dataframe(plan['return'],hide_index=True,width='stretch')
            st.caption(plan['limitation'])
            if plan.get('schedule_check'):
                st.write('Comprobación de todos los turnos seleccionados: '+plan['schedule_check']['status'])
                st.dataframe([{'Entrada':r['start'],'Salida':r['end'],'Ida y vuelta programadas':r['scheduled_round_trip_found'],'Retención':r.get('hold_reason','')} for r in plan['schedule_check']['shifts']],hide_index=True)
            st.warning('El cálculo de horarios no verifica el paseo, el domicilio, los demás días ni la dirección exacta del empleo. Guarda la comprobación manual de abajo cuando hayas contrastado esos datos.')
    except Exception as exc:
        st.error('Horarios no disponibles: '+str(exc))
