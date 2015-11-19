from contextlib import contextmanager
import logging
from collections import OrderedDict
import time

from librato_python_web.instrumentor import context
from librato_python_web.statsd.client import statsd_client
from librato_python_web.instrumentor.util import AliasGenerator, Timing

logger = logging.getLogger(__name__)


# noinspection PyClassHasNoInit
class _global:
    reporter = None
    """:type: TelemetryReporter"""


def set_reporter(reporter):
    """
    Sets the reporter for configuration information.

    Defaults to StdoutConfigReporter.

    :param reporter: the reporter instance
    :type reporter: TelemetryReporter
    """
    _global.reporter = reporter


def count(metric, incr=1):
    """
    Increment the count for the given metric by the given increment.

    Example
        telemetry.count('requests')
        telemetry.count('bytesReceived', len(request.content))

    :param metric: the given metric name
    :param incr: the value by which it is incremented
    """
    return _global.reporter.count(metric, incr)


def record(metric, value):
    """
    Records a given value as a data point for the given metric at the current timestamp.

    The current of the context stack is included.

    Example
        telemetry.record('maxHeap', max_heap_size)

    :param metric: the given metric name
    :param value: the value to be recorded
    """
    return _global.reporter.record(metric, value)


def event(event_type, dictionary=None):
    """
    Reports an event of a given type.

    dict provides optional additional values. Valid dictionary values include:
    * id: unique identifier for this event (defaults to generated UUID4 string)
    * message: descriptive string value (optional)

    Example
        telemetry.event('new-account', {
            'id':'a039fdf8-66e4-4ac9-8d83-51179d395984',
            'message': 'Created new user account',
            'user': 'test@example.com',
            'account': '437fbd24-5dd3-45f1-9fb3-c86db5283c8d'

        })
    :param event_type: descriptor for event type
    :param dictionary: additional values for event
    """
    _global.reporter.event(event_type, dictionary)


def default_instrumentation(type_name='resource'):
    @contextmanager
    def wrapper_func(*args, **keywords):
        Timing.start_timer(type_name)
        try:
            yield
        finally:
            elapsed = Timing.stop_timer(type_name)
            record_telemetry(type_name, elapsed)

    return wrapper_func


def record_telemetry(type_name, elapsed):
    count(type_name + 'requests')
    record(type_name + 'latency', elapsed)


def generate_record_telemetry(type_name):
    return lambda elapsed: record_telemetry(type_name, elapsed)


"""
class GeneratorWrapper(object):
    def __init__(self, wrapped, type_name):
        self.wrapped = wrapped
        self.elapsed = 0
        self.type_name = type_name

    def __enter__(self):
        t = time.clock()
        self.iterator = self.wrapped()
        self.elapsed += time.clock()-t
        print 'enter', self.elapsed, v

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()  # Python 3

    def next(self):
        t = time.clock()
        v = self.iterator()
        self.elapsed += time.clock()-t
        print 'next', self.elapsed, v
        yield v

    def __exit__(self):
        print 'exit', self.type_name, self.elapsed
        try:
            count(self.type_name + 'requests')
        finally:
            record(self.type_name + 'latency', self.elapsed)


def default_generator_instrumentation(type_name='resource'):
    @contextmanager
    def wrapper_func(*args, **keywords):
        Timing.start_timer(type_name)
        try:
            if not keywords.get('additional_work', False):
                count(type_name + 'requests')
            yield
        finally:
            elapsed = Timing.stop_timer(type_name)
            record(type_name + 'latency', elapsed)

    return wrapper_func
"""


def increment_count(type_name='resource'):
    @contextmanager
    def wrapper_func(*args, **keywords):
        count(type_name + 'requests')
        yield

    return wrapper_func


class TelemetryReporter(object):
    def __init__(self):
        super(TelemetryReporter, self).__init__()

    def count(self, metric, incr=1):
        pass

    def record(self, metric, value):
        pass

    def event(self, type_name, dictionary=None):
        pass


class StdoutTelemetryReporter(TelemetryReporter):
    def __init__(self):
        super(StdoutTelemetryReporter, self).__init__()

    def count(self, metric, incr=1):
        print metric, context.get_tags(), incr

    def record(self, metric, value):
        print metric, context.get_tags(), value

    def event(self, type_name, dictionary=None):
        print type_name, context.get_tags(), dictionary


class StatsdTelemetryReporter(TelemetryReporter):
    def __init__(self, port=8142):
        super(StatsdTelemetryReporter, self).__init__()
        self.client = statsd_client.Client(port=port)

    def count(self, metric, incr=1):
        self.client.increment(metric, incr)

    def record(self, metric, value):
        # traceback.print_stack()
        self.client.timing(metric, value * 1000)

    def event(self, type_name, dictionary=None):
        # TBD: Not implemented
        pass

    def _register_alias(self, alias, value):
        logger.debug("registering alias %s->%s", alias, value)
        self.client.define_alias(alias, value)


class StatsdTaggingTelemetryReporter(TelemetryReporter):
    def __init__(self):
        super(StatsdTaggingTelemetryReporter, self).__init__()
        self.client = statsd_client.Client()
        self.aliases = AliasGenerator()

    def count(self, metric, incr=1):
        self.client.increment(metric, incr, tags=self.get_tags_dict())

    def record(self, metric, value):
        self.client.gauge(metric, value, tags=self.get_tags_dict())

    def event(self, type_name, dictionary=None):
        # TBD: Not implemented
        pass

    def get_tags_dict(self):
        tags = OrderedDict()
        for key, value in context.get_tags():
            alias = self.aliases.get_alias(value)
            if alias:
                value = alias
            elif self.aliases.needs_alias(value):
                alias = self.aliases.generate_alias(value)
                self._register_alias(alias, value)
                value = alias
            tags[key] = value
        return tags

    def _register_alias(self, alias, value):
        self.client.define_alias(alias, value)


set_reporter(StdoutTelemetryReporter())
