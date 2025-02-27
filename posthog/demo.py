from posthog.models import Person, PersonDistinctId, Event, Element, Action, ActionStep, Funnel, FunnelStep, Team
from dateutil.relativedelta import relativedelta
from django.utils.timezone import now
from django.http import HttpResponseNotFound, JsonResponse

from posthog.urls import render_template
from posthog.utils import render_template

from typing import List
from pathlib import Path
import uuid

import random
import json

def _create_anonymous_users(team: Team, base_url: str) -> None:
    with open(Path('posthog/demo_data.json').resolve(), 'r') as demo_data_file:
        demo_data = json.load(demo_data_file)

    Person.objects.bulk_create([
        Person(team=team, properties={'is_demo': True}) for _ in range(0, 100)
    ])
    distinct_ids: List[PersonDistinctId] = []
    events: List[Event] = []
    days_ago = 7
    demo_data_index = 0
    for index, person in enumerate(Person.objects.filter(team=team)):
        if index > 0 and index % 14 == 0:
            days_ago -= 1

        distinct_id = str(uuid.uuid4())
        distinct_ids.append(PersonDistinctId(team=team, person=person, distinct_id=distinct_id))
        date = now() - relativedelta(days=days_ago)
        browser = random.choice(['Chrome', 'Safari', 'Firefox'])
        events.append(Event(team=team, event='$pageview', distinct_id=distinct_id, properties={'$current_url': base_url, '$browser': browser, '$lib': 'web'}, timestamp=date))
        if index % 3 == 0:
            person.properties.update(demo_data[demo_data_index])
            person.save()
            demo_data_index += 1
            Event.objects.create(
                team=team,
                distinct_id=distinct_id,
                event='$autocapture',
                properties={'$current_url': base_url},
                timestamp=date + relativedelta(seconds=14),
                elements=[
                    Element(tag_name='a', href='/demo/1', attr_class=['btn', 'btn-success'], attr_id='sign-up', text='Sign up')
                ])
            events.append(Event(event='$pageview', team=team, distinct_id=distinct_id, properties={'$current_url': '%s1/' % base_url, '$browser': browser, '$lib': 'web'}, timestamp=date + relativedelta(seconds=15)))
            if index % 4 == 0:
                Event.objects.create(
                    team=team,
                    event='$autocapture',
                    distinct_id=distinct_id,
                    properties={'$current_url': '%s1/' % base_url},
                    timestamp=date + relativedelta(seconds=29),
                    elements=[
                        Element(tag_name='button', attr_class=['btn', 'btn-success'], text='Sign up!')
                    ])
                events.append(Event(event='$pageview', team=team, distinct_id=distinct_id, properties={'$current_url': '%s2/' % base_url, '$browser': browser, '$lib': 'web'}, timestamp=date + relativedelta(seconds=30)))
                if index % 5 == 0:
                    Event.objects.create(
                        team=team,
                        event='$autocapture',
                        distinct_id=distinct_id,
                        properties={'$current_url': '%s2/' % base_url},
                        timestamp=date + relativedelta(seconds=59),
                        elements=[
                            Element(tag_name='button', attr_class=['btn', 'btn-success'], text='Pay $10')
                        ])
                    events.append(Event(event='$pageview', team=team, distinct_id=distinct_id, properties={'$current_url': '%s3/' % base_url, '$browser': browser, '$lib': 'web'}, timestamp=date + relativedelta(seconds=60)))

    PersonDistinctId.objects.bulk_create(distinct_ids)
    Event.objects.bulk_create(events)

def _create_funnel(team: Team, base_url: str) -> None:
    homepage = Action.objects.create(team=team, name='HogFlix homepage view')
    ActionStep.objects.create(action=homepage, event='$pageview', url=base_url, url_matching='exact')

    user_signed_up = Action.objects.create(team=team, name='HogFlix signed up')
    ActionStep.objects.create(action=homepage, event='$autocapture', url='%s1/' % base_url, url_matching='exact', selector='button')

    user_paid = Action.objects.create(team=team, name='HogFlix paid')
    ActionStep.objects.create(action=homepage, event='$autocapture', url='%s2/' % base_url, url_matching='exact', selector='button')

    funnel = Funnel.objects.create(team=team, name='HogFlix signup -> watching movie')
    FunnelStep.objects.create(funnel=funnel, action=homepage, order=0)
    FunnelStep.objects.create(funnel=funnel, action=user_signed_up, order=1)
    FunnelStep.objects.create(funnel=funnel, action=user_paid, order=2)

def demo(request):
    team = request.user.team_set.get()
    if Event.objects.filter(team=team).count() == 0:
        _create_funnel(team=team, base_url=request.build_absolute_uri('/demo/'))
        _create_anonymous_users(team=team, base_url=request.build_absolute_uri('/demo/'))
    return render_template('demo.html', request=request, context={'api_token': team.api_token})

def delete_demo_data(request):
    team = request.user.team_set.get()

    people = PersonDistinctId.objects.filter(team=team, person__properties__is_demo=True)
    Event.objects.filter(team=team, distinct_id__in=people.values('distinct_id')).delete()
    Person.objects.filter(team=team, properties__is_demo=True).delete()
    Funnel.objects.filter(team=team, name__contains="HogFlix").delete()
    Action.objects.filter(team=team, name__contains="HogFlix").delete()

    return JsonResponse({'status': 'ok'})