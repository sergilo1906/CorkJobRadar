"""Normalize published HSE local deadlines without guessing unrecognized formats."""
from datetime import datetime


def hse_deadline_fields(fields):
    closing=next((value for key,value in fields.items() if key.strip().casefold()=='closing date'),None)
    if not closing:return {}
    result={'application_deadline_original':closing}
    if not isinstance(closing,str):return result
    for pattern in ('%d/%m/%Y %H:%M:%S','%d/%m/%Y %H:%M','%d/%m/%Y'):
        try:
            parsed=datetime.strptime(' '.join(closing.split()),pattern)
            result.update(application_deadline=parsed.date().isoformat() if pattern=='%d/%m/%Y' else parsed.isoformat(),
                          deadline_timezone='Europe/Dublin',
                          deadline_interpretation='Fecha/hora publicada por HSE Irlanda; zona local de contratación irlandesa')
            break
        except ValueError:continue
    return result
