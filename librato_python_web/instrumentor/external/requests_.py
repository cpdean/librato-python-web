# Copyright (c) 2015. Librato, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Librato, Inc. nor the names of project contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL LIBRATO, INC. BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from math import floor

from librato_python_web.instrumentor.base_instrumentor import BaseInstrumentor
from librato_python_web.instrumentor.instrument import instrument_methods_v2, _should_be_instrumented
from librato_python_web.instrumentor import context as context
from librato_python_web.instrumentor import telemetry
from librato_python_web.instrumentor.util import get_parameter, Timing


def _session_send_wrapper(func, *args, **keywords):
    if not _should_be_instrumented(state='external', enable_if='web', disable_if='model'):
        return func(*args, **keywords)

    telemetry.count('external.http.requests')
    Timing.push_timer()
    try:
        context.push_state('external')
        a = func(*args, **keywords)
        telemetry.count('external.http.status.%ixx' % floor(a.status_code / 100))
        return a
    except:
        telemetry.count('external.http.errors')
        raise
    finally:
        context.pop_state('external')
        elapsed, _ = Timing.pop_timer()
        telemetry.record('external.http.response.latency', elapsed)


class RequestsInstrumentor(BaseInstrumentor):
    modules = {'requests.sessions': ['Session']}

    def __init__(self):
        super(RequestsInstrumentor, self).__init__(
            {
                # External calls are not recorded when in the context of a model operation
                'requests.sessions.Session.send': _session_send_wrapper,
            }
        )

    def run(self):
        instrument_methods_v2(self.wrapped_methods)
