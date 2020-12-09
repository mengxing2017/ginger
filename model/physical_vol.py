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

from wok.plugins.ginger.model import utils

from wok.plugins.ginger.model.dasd_utils import change_dasdpart_type
from wok.plugins.ginger.model.diskparts import PartitionModel
from wok.asynctask import AsyncTask
from wok.exception import MissingParameter, NotFoundError
from wok.exception import InvalidParameter, OperationFailed
from wok.model.tasks import TaskModel


class PhysicalVolumesModel(object):
    """
    Model class for listing and creating a PV
    """
    def __init__(self, **kargs):
        self.objstore = kargs['objstore']
        self.task = TaskModel(**kargs)

    def create(self, params):

        if 'pv_name' not in params:
            raise MissingParameter("GINPV00001E")

        pvname = params['pv_name']

        taskid = AsyncTask(u'/pvs/pv_name/%s' % (pvname),
                           self._create_task, params).id

        return self.task.lookup(taskid)

    def _create_task(self, cb, params):

        pvname = params['pv_name']

        cb('entering task to create pv')
        try:

            cb('create pv')
            part = PartitionModel(objstore=self.objstore)
            part_name = pvname.split('/')[-1]
            dev_type = part.lookup(part_name)
            if dev_type['type'] == 'part':
                if 'dasd' in dev_type['name']:
                    type = '4'
                    change_dasdpart_type(part_name, type)
                else:
                    type = '8e'   # hex value for type Linux LVM
                    part.change_type(part_name, type)
            utils._create_pv(pvname)

        except OperationFailed:
            raise OperationFailed("GINPV00002E",
                                  {'name': pvname})

        cb('OK', True)

    def get_list(self):

        try:
            pv_names = utils._get_pv_devices()
        except OperationFailed as e:
            raise NotFoundError("GINPV00003E",
                                {'err': e.message})

        return pv_names


class PhysicalVolumeModel(object):
    """
    Model for viewing and deleting a PV
    """
    def __init__(self, **kargs):
        self.objstore = kargs['objstore']
        self.task = TaskModel(**kargs)

    def lookup(self, name):
        try:
            return utils._pvdisplay_out(name)

        except OperationFailed:
            raise NotFoundError("GINPV00004E", {'name': name})

    def delete(self, name):
        try:
            utils._remove_pv(name)
        except OperationFailed as e:
            raise InvalidParameter("GINPV00005E", {'err': e.message})
