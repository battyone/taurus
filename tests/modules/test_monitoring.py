import logging
import random
import time
import datetime

from bzt.modules.monitoring import Monitoring, MonitoringListener, MonitoringCriteria
from bzt.modules.monitoring import ServerAgentClient, GraphiteClient, LocalClient
from bzt.modules.provisioning import Local
from bzt.utils import BetterDict
from tests import BZTestCase
from tests.mocks import EngineEmul, SocketEmul


class TestMonitoring(BZTestCase):
    def test_server_agent(self):
        obj = Monitoring()
        obj.engine = EngineEmul()
        obj.parameters.merge({
            "server-agent": [{
                "address": "127.0.0.1:4444",
                "metrics": [
                    "cpu",
                    "disks"
                ]
            }, {
                "address": "10.0.0.1",
                "metrics": [
                    "something1",
                    "something2"
                ]
            }]
        })

        listener = LoggingMonListener()
        obj.add_listener(listener)

        widget = obj.get_widget()
        obj.add_listener(widget)

        crit_conf = BetterDict()
        crit_conf.merge({"threshold": 5, "subject": "127.0.0.1:4444/cpu"})
        criteria = MonitoringCriteria(crit_conf, obj)
        obj.add_listener(criteria)

        obj.client_classes = {'server-agent': ServerAgentClientEmul}

        obj.prepare()
        obj.startup()

        for _ in range(1, 10):
            obj.clients[0].socket.recv_data += "%s\t%s\n" % (random.random(), random.random())
            obj.check()
            logging.debug("Criteria state: %s", criteria)
            time.sleep(1)

        obj.shutdown()
        obj.post_process()

        self.assertEquals("test\ninterval:1\nmetrics:cpu\tdisks\nexit\n", obj.clients[0].socket.sent_data)

    def test_graphite(self):
        obj = Monitoring()
        obj.engine = EngineEmul()
        obj.parameters.merge({
            "graphite": [{
                "address": "people.com:1066",
                "label": "Earth",
                "metrics": [
                    "body",
                    "brain"]}, {
                "address": "http://spirits.net",
                "metrics": [
                    "transparency",
                    "usability"
                ]}]
        })
        obj.client_classes = {'graphite': GraphiteClientEmul}
        obj.prepare()
        obj.startup()
        obj.check()

        obj.clients[0].check_time -= obj.clients[0].interval * 2
        obj.check()

        obj.clients[0].check_time -= obj.clients[0].interval * 2
        obj.clients[0].prepared_data = "wrong data"
        obj.check()

        obj.shutdown()
        obj.post_process()

    def test_local_with_engine(self):
        config = {'metrics': ['cpu', 'engine-loop']}
        obj = LocalClient(logging.getLogger(''), 'label', config)
        obj.engine = EngineEmul()
        data = obj.get_data()
        self.assertTrue(all('source' in item.keys() and 'ts' in item.keys() for item in data))
        return data

    def test_local_without_engine(self):
        config = {'metrics': ['cpu']}
        obj = LocalClient(logging.getLogger(''), 'label', config)
        data = obj.get_data()
        self.assertTrue(all('source' in item.keys() and 'ts' in item.keys() for item in data))
        return data


class LoggingMonListener(MonitoringListener):
    def monitoring_data(self, data):
        logging.debug("Data: %s", data)


class ServerAgentClientEmul(ServerAgentClient):
    def __init__(self, parent_logger, label, config):
        super(ServerAgentClientEmul, self).__init__(parent_logger, label, config)
        self.socket = SocketEmul()
        self.socket.recv_data = "Yep\n"
        self.select = self.select_emul

    def select_emul(self, reads, writes, excepts, timeout):
        return reads, writes, []


class LocalProvisioningTest(BZTestCase):
    def test_start_shift(self):
        local = Local()

        _today = datetime.date.today()
        _yesterday = _today - datetime.timedelta(days=1)
        _tomorrow = _today + datetime.timedelta(days=1)
        _start_time = datetime.time(12, 30, 5)
        _shedule_time = datetime.time(13, 31, 7)

        local.start_time = time.mktime(datetime.datetime.combine(_today, _start_time).timetuple())

        date = datetime.datetime.combine(_tomorrow, _shedule_time).strftime('%Y-%m-%d %H:%M:%S')
        shift = local._get_start_shift(date, '')
        self.assertEqual(shift, 90062.0)

        date = datetime.datetime.combine(_yesterday, _shedule_time).strftime('%Y-%m-%d %H:%M')
        shift = local._get_start_shift(date, '')
        self.assertEqual(shift, 3655.0)

        date = datetime.datetime.combine(_today, _shedule_time).strftime('%H:%M:%S')
        shift = local._get_start_shift(date, '')
        self.assertEqual(shift, 3662.0)

        date = datetime.datetime.combine(_today, _shedule_time).strftime('%H:%M')
        shift = local._get_start_shift(date, '')
        self.assertEqual(shift, 3655.0)

        date = datetime.datetime.combine(_today, _shedule_time).strftime('%m/%d/%y %H:%M:%S')
        shift = local._get_start_shift(date, '%m/%d/%y %H:%M:%S')
        self.assertEqual(shift, 3662.0)

        shift = local._get_start_shift('', '')
        self.assertEqual(shift, 0)

        shift = local._get_start_shift('lorem ipsum', 'bla-bla-bla')
        self.assertEqual(shift, 0)


class GraphiteClientEmul(GraphiteClient):
    prepared_data = [{'target': 'usability', 'datapoints': [[1, 1], [2, 2]]}]

    def _data_transfer(self):
        return self.prepared_data
