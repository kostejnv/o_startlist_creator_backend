import imp
import json
from django.http import HttpResponse, JsonResponse
from minizinc import Instance, Model, Solver
from django.core.mail import send_mail
from o_startlist_creator.logic.event import Event, parse_event
from o_startlist_creator.logic.solver import Solver as MainSolver
from o_startlist_creator.logic.email_sender import EmailSender
import os

from types import SimpleNamespace
import multiprocessing
import logging
import datetime

from o_startlist_creator.logic.validator import EmailValidator

with open(os.path.join(os.path.dirname(__file__), '../../.secrets/communication_key')) as f:
    SECURITY_KEY = f.read().strip()

def hello(request, name):
    return HttpResponse(f"<h2>Hello {name} 2.0</h2>")

def minizinc(request, n):
    # Load n-Queens model from file
    nqueens = Model()
    nqueens.add_string("""
        int: n; % The number of queens.

        array [1..n] of var 1..n: q;

        include "alldifferent.mzn";

        constraint alldifferent(q);
        constraint alldifferent(i in 1..n)(q[i] + i);
        constraint alldifferent(i in 1..n)(q[i] - i);"""
    )
    # Find the MiniZinc solver configuration for Gecode
    gecode = Solver.lookup("gecode")
    # Create an Instance of the n-Queens model for Gecode
    instance = Instance(gecode, nqueens)
    # Assign 4 to n
    instance["n"] = int(n)
    result = instance.solve()
    # Output the array q
    return HttpResponse(f'<h2>{result["q"]}</h2>')

def send_me_email(request):
    send_mail('Django', "Toto je zkouska posilani emailu", 'v.kostejn.experimental@gmail.com', ['v.kostejn.vk@gmail.com'], fail_silently=False)
    return HttpResponse("Email was sent")


def get_event(request) -> json:
    if request.method == "POST" and request.accepts("application/json"):
        get_data = json.loads(request.body, object_hook=lambda d: SimpleNamespace(**d))
        if get_data.security_key == SECURITY_KEY:
            oris_id = get_data.oris_id
            courses_str = get_data.courses_str
            event = Event()

            try:
                event.add_dat_from_oris(oris_id)
            except Exception as e:
                return HttpResponse(status=501)
            try:
                event.add_data_from_courses_file(courses_str)
            except Exception as e:
                return HttpResponse(status=502)

            return JsonResponse(event.export_input_data_to_dict())
    return HttpResponse(status=404)


def solve_event(request) -> None:
    if request.method == 'POST' and request.accepts("application/json"):
        post_data = json.loads(request.body, object_hook=lambda d: SimpleNamespace(**d))
        if post_data.security_key == SECURITY_KEY:
            try:
                json_event = post_data.event
                email = post_data.email
                if not EmailValidator(email).validate():
                    return HttpResponse(status=503)
                try:
                    event = parse_event(json_event)
                except ImportError:
                    return HttpResponse(status=502)
                except Exception as e:
                    return HttpResponse(status=501)
                multiprocessing.Process(target=solve_and_send, args=[event, email]).start()
                return HttpResponse(status=200)
            except:
                return HttpResponse(status=500)
    return HttpResponse(status=404)

def solve_and_send(event:Event, email:str):
    """
        function for multiproccessing
    """


    try:
        event = MainSolver().solve(event)
        EmailSender().send(email, event)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"{datetime.datetime.now()} - {e.args}")


def DEBUG_get_table(event_json, entries_json, courses_file) -> json:
    event = Event()
    event.DEBUG_add_dat_from_oris(event_json, entries_json)
    event.add_data_from_courses_file(courses_file)
    return event.export_input_data_to_dict()

# if __name__ == '__main__':
#     minizinc(None)