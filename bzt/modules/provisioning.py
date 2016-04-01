"""
Implementations for `Provisioning` classes

Copyright 2015 BlazeMeter Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import time
import datetime


from bzt.engine import Provisioning
from bzt.utils import dehumanize_time


class Local(Provisioning):
    """
    Local provisioning means we start all the tools locally
    """
    def _get_start_shift(self, shift, time_format):

        if shift == '':
            return 0

        if time_format != '':
            time_formats = [time_format]
        else:
            time_formats = ['%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%d %H:%M',
                            '%H:%M:%S',
                            '%H:%M']

        for time_format in time_formats:
            try:
                date = datetime.datetime.strptime(shift, time_format)
            except ValueError:
                continue
            except TypeError:
                self.log.warning('Start time must be string type, ignored')
                break
            today = datetime.date.today()
            if today > date.date():
                date = datetime.datetime(today.year, today.month, today.day, date.hour, date.minute, date.second)
            return time.mktime(date.timetuple()) - self.start_time
        else:
            self.log.warning('Unrecognized time format: %s, ignored', shift)

        return 0

    def prepare(self):
        """
        Call prepare on executors
        """
        super(Local, self).prepare()

        self.start_time = time.time()

        for executor in self.executors:
            self.log.debug("Preparing executor: %s", executor)
            executor.prepare()
            self.engine.prepared.append(executor)

            user_time_format = executor.execution.get('time-format', '')
            start_shift = self._get_start_shift(executor.execution.get('start-at', ''), user_time_format)
            delay = dehumanize_time(executor.execution.get('delay', '0'))
            executor.delay = delay + start_shift
            self.log.debug("Delay setup: %s(start-at) + %s(delay) = %s", start_shift, delay, executor.delay)

    def startup(self):
        pass

    def _start_modules(self):
        for executor in self.executors:
            if executor in self.engine.prepared and executor not in self.engine.started:
                if time.time() >= self.start_time + executor.delay:  # time to start executor
                    executor.startup()
                    self.engine.started.append(executor)

    def check(self):
        """
        Check executors for finish. Return True if all of them has finished.
        """
        finished = True

        self._start_modules()
        for executor in self.executors:
            if executor in self.engine.started:
                finished &= executor.check()
            else:
                finished = False

        return finished

    def shutdown(self):
        """
        Call shutdown on executors
        """
        for executor in self.executors:
            if executor in self.engine.started:
                self.log.debug("Shutdown %s", executor)
                executor.shutdown()

    def post_process(self):
        """
        Post-process executors
        """
        for executor in self.executors:
            if executor in self.engine.prepared:
                self.log.debug("Post-process %s", executor)
                executor.post_process()
