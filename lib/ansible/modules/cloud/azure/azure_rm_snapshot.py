#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
# TODO: Work in progress


from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
author: "Emma Laurijssens van Engelenhoven, building on the module built by Derrick Sutherland"
description:
  - "Capture an Azure Virtual Machine managed image to create other managed virtual machines with. 
     The VM should be generalized usimg sysprep. After this command runs, the Virtual Machine will be unusable.
     Depends on pip azure module 2.0.0 or above and azure-mgmt-compute 2.1.0 and above."
module: azure_managed_image_capture
options:
  resource_group:
    description:
      - "The resource group name to use or create to host the deployed template"
    required: true
  subscription_id:
    description:
      - "The Azure subscription to deploy the template into."
    required: true
  tenant_id:
    description:
      - "The Azure Active Directory tenant ID of the subscription."
    required: true
  client_id:
    description:
      - "The Azure Active Directory tenant ID of the subscription."
    required: true
  image_name:
    description:
      - "The name of the image being created."
    required: true
  vm_name:
    description:
      - "The name of the VM within the resource group to capture"
    required: true
  location:
    description:
      - "The location where the image should be stored. Should be within the resource group."
    default: westus
    required: true
        
short_description: "Capture Azure Virtual Machine Images"
version_added: "2.0"

'''

EXAMPLES = '''
- name: Capture image
  hosts: 127.0.0.1
  connection: local

  tasks:
    - name: Capture image
      azure_managed_image_capture:
        subscription_id: "{{ subscription_id }}"
        resource_group: "{{ resource_group }}"
        image_name: "{{ vm-name }}-image"
        client_id: "{{ secrets.client_id }}"
        tenant_id: "{{ tenant_id }}"
        client_secret: "{{ secrets.client_secret }}"
        vm_name: "{{ vm_name }}"
        location: "{{ location }}"
      register: capture_info
'''

RETURN = '''
azure_managed_disk:
    description: List of managed disk dicts.
    returned: always
    type: list
'''

from ansible.module_utils.azure_rm_common import AzureRMModuleBase
import jsonpickle
import json

try:
    from msrestazure.azure_exceptions import CloudError
    from azure.mgmt.compute.models import Snapshot

except:
    pass

class AzureRMVMSnapshot(AzureRMModuleBase):
    def __init__(self):

        self.module_arg_spec = dict(
            resource_group=dict(
                type='str',
                required=True
            ),
            name=dict(
                type='str',
                required=True
            ),
            prefix=dict(
                type='str',
                required=False
            ),
            suffix=dict(
                type='str',
                required=False
            ),
            location=dict(
                type='str',
                required=False
            ),
            state=dict(
                type='str',
                required=False,
                default='present',
                choices=['present', 'absent']
            )
        )
        self.results = dict(
            ansible_facts=dict(
                azure_snapshot=[]
            )
        )
        self.resource_group = None
        self.name = None
        self.prefix = None
        self.suffix = None
        self.state = None
        self.location = None

        self.results = dict(
            changed=False,
            actions=[],
            ansible_facts=dict(azure_snapshot=None)
        )

        super(AzureRMVMSnapshot, self).__init__(
            derived_arg_spec=self.module_arg_spec,
            supports_check_mode=False)

    def exec_module(self, **kwargs):

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        try:
            resource_group = self.get_resource_group(self.resource_group)
        except CloudError:
            self.fail(
                'resource group {} not found'
                .format(self.resource_group))
        if not self.location:
            self.location = resource_group.location
        if self.state == 'present':
            self.results['state'] = self.create_snapshot()
        elif self.state == 'absent':
            self.delete_snapshot()
        return self.results

    def create_snapshot(self):

        snapshot = self.compute_client.snapshots

        try:
            vms = self.compute_client.virtual_machines
            vm = vms.get(resource_group_name=self.resource_group, vm_name=self.name)
        except CloudError:
            self.fail("VM {} not found!".format(self.name))
        except Exception as e:
            self.fail("An exception occurred: {}".format(str(e)))

        managed = not (vm.storage_profile.os_disk.managed_disk is None)

        data_disks = vm.storage_profile.data_disks

        result = dict(snap=json.loads(jsonpickle.encode(vm)),
                      managed=managed
        )


        # disks = [dict(name=snap.storage_profile.os_disk.managed_disk.id.rsplit('/', 1)[-1],
        #               id=snap.storage_profile.os_disk.managed_disk.id)]
        #
        # for disk in data_disks:
        #     disks.append(dict(name=disk.managed_disk.id.rsplit('/', 1)[-1],
        #                       id=disk.managed_disk.id))
        #
        # results = []
        #
        # for disk in disks:
        #
        #     creation_data = dict(createOption="Copy",
        #                          sourceResourceId=disk["id"])
        #
        #     results.append(creation_data)
        #
        #     snap_source = Snapshot(location=self.location,
        #                            creation_data=creation_data,
        #                            sku=dict(name="Standard_LRS"))
        #     try:
        #         operation = snapshot.create_or_update(resource_group_name=self.resource_group,
        #                                               snapshot_name="{}{}{}".format(self.prefix,
        #                                                                             disk["name"],
        #                                                                             self.suffix),
        #                                               snapshot=snap_source)
        #     except CloudError as e:
        #         self.fail("Snapshot could not be created: {}".format(str(e)))
        #     except Exception as e:
        #         self.fail("An exception occurred: {}".format(str(e)))
        #
        #     operation.wait()
        #
        #     results.append(operation.result())
        #
        # result = json.loads(jsonpickle.encode(results))
        #
        return result

    def delete_snapshot(self):
        pass


def main():

    AzureRMVMSnapshot()

# import module snippets

if __name__ == '__main__':
    main()
