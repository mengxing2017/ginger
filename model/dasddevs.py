# -*- coding: utf-8 -*-
#
# Project Ginger
#
# Copyright IBM Corp, 2016
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA

from wok.plugins.ginger.model import dasd_utils
import platform
import threading

from wok.asynctask import AsyncTask
from wok.exception import InvalidOperation, MissingParameter
from wok.exception import NotFoundError, OperationFailed
from wok.model.tasks import TaskModel
from wok.utils import run_command

# Max no of permitted concurrent DASD format operations
MAX_DASD_FMT = 24


class DASDdevsModel(object):
    """
    Model class for listing DASD devices (lsdasd -l)
    """

    @staticmethod
    def is_feature_available():
        _, _, returncode = run_command(['lsdasd', '-l'])
        ptfm = platform.machine()
        if ptfm != 's390x' or returncode != 0:
            return False
        else:
            return True

    def get_list(self):
        try:
            dasd_devs = dasd_utils._get_lsdasd_devs()
        except OperationFailed as e:
            raise OperationFailed("GINDASD0005E", {'err': e.message})

        return dasd_devs


class DASDdevModel(object):
    """
    Model for viewing and formatting a DASD device
    """

    def __init__(self, **kargs):
        self.objstore = kargs['objstore']
        self.task = TaskModel(**kargs)
        self.dev_details = {}

    def lookup(self, bus_id):
        dasd_utils.validate_bus_id(bus_id)
        try:
            dasddevices = dasd_utils._get_dasd_dev_details(bus_id)
            self.dev_details = dasddevices[0]
        except IndexError as e:
            raise NotFoundError("GINDASD0006E",
                                {'name': bus_id, 'err': e.message})

        return self.dev_details

    def format(self, bus_id, blk_size):
        tasks = []
        dasd_utils.validate_bus_id(bus_id)
        woklock = threading.Lock()
        name = self.dev_details['name']
        dasd_name_list = dasd_utils._get_dasd_names()
        if name not in dasd_name_list:
            raise NotFoundError('GINDASD0007E')
        task_params = {'blk_size': blk_size, 'name': name}
        try:
            woklock.acquire()
            with self.objstore as session:
                tasks = session.get_list('task')

            running_tasks = []
            for task in tasks:
                with self.objstore as session:
                    current_task = session.get('task', str(task))
                    if (current_task['target_uri'].startswith('/dasddevs') and
                       current_task['status']) == 'running':
                        running_tasks.append(current_task)

            # Limit the number of concurrent DASD format operations to
            # MAX_DASD_FMT.
            if len(running_tasks) > MAX_DASD_FMT:
                raise InvalidOperation(
                    "GINDASD0014E", {
                        'max_dasd_fmt': str(MAX_DASD_FMT)})

            taskid = AsyncTask(u'/dasddevs/%s/blksize/%s' % (name, blk_size),
                               self._format_task, task_params).id
        except OperationFailed:
            woklock.release()
            raise OperationFailed("GINDASD0008E", {'name': name})
        finally:
            woklock.release()

        return self.task.lookup(taskid)

    def _format_task(self, cb, params):
        if 'name' not in params:
            raise MissingParameter("GINDASD0009E")
        name = params['name']

        if 'blk_size' not in params:
            raise MissingParameter("GINDASD0010E")
        blk_size = params['blk_size']

        try:
            dasd_utils._format_dasd(blk_size, name)
        except OperationFailed:
            raise OperationFailed('GINDASD0008E', {'name': name})

        cb('OK', True)
