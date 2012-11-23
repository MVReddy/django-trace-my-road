from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.utils import simplejson as json

from traces.models import Trace, MongoJSONEncoder
from annoying.decorators import render_to
from locations.helpers import location_from_request

from datetime import datetime


def get_traces(request):
    """ Returns Traces associated with User if authenticated, otherwise session-associated.""" 
    if request.user.is_authenticated():
        return Trace.objects.filter(user=request.user).order_by('-created')
    elif 'traces' in request.session:
        return Trace.objects.filter(uuid__in=request.session['traces']).order_by('-created')
    return Trace.objects.none()


@render_to('traces/index.html')
def index(request, country_slug=None, city_slug=None):
    """ A Home page """
    location = location_from_request(request)
    center = (location['latitude'], location['longitude'])
    city = location['city']
    traces = get_traces(request)
    return locals()
    
    
@render_to('traces/trace_object.html')
def trace_object(request, trace_uuid):
    """ Displays detail of the given Trace.
    Updates related mongo instance if necessary 
    (Serves regular GET and Ajax PUT from Backbone.js). """

    trace = get_object_or_404(Trace, uuid=trace_uuid)
    location = location_from_request(request)
    center = (location['latitude'], location['longitude'])

    fire_start = 'fire_start' in request.GET
    db = Trace.mongo_objects.db
    traces_mongo = db.find_one(dict(uuid=trace.uuid))
    if not traces_mongo:
        traces_mongo = dict(uuid=trace.uuid, points=[])
        db.insert(traces_mongo)

    if request.method == 'PUT':
        trace_dict = json.loads(request.raw_post_data)
        if 'points' in trace_dict:
            traces_mongo['points'].extend(trace_dict['points'])
            db.save(traces_mongo)
        return HttpResponse(json.dumps(traces_mongo, cls=MongoJSONEncoder))

    traces = get_traces(request).exclude(pk=trace.pk)
    points = traces_mongo and traces_mongo['points'] or []
    points = json.dumps(points)
    return locals()


@render_to('traces/trace_list.html')
def trace_list(request):
    """ Users's trace list """
    print 'trace_list', request.POST
    is_authenticated = request.user.is_authenticated()
    if is_authenticated:
        traces = Trace.objects.filter(user=request.user)
    else:
        traces = Trace.objects.filter(uuid__in=[uuid for uuid in request.session.get('traces', [])])
    return locals()


def start_record(request):
    """ Creates Trace object and redirects to trace detail view. """
    is_authenticated = request.user.is_authenticated()
    if is_authenticated:
        kwargs = dict(user=request.user)
    else:
        kwargs = {}
    trace = Trace.objects.create(**kwargs)
    if not is_authenticated:
        # put traces into user session.
        traces = request.session.get('traces', [])
        traces.append(trace.uuid)
        request.session['traces'] = traces
    Trace.mongo_objects.db.insert(dict(uuid=trace.uuid, points=[]))
    return HttpResponseRedirect(reverse('trace-object', args=[trace.uuid]) + '?fire_start')
    
