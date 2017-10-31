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

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
---
author: "Emma Laurijssens van Engelenhoven"
description:
  - "Capture an Azure Virtual Machine image for the deployment of other VMs in Azure 
     The VM should be generalized usimg sysprep. After this command runs, the Virtual Machine will be unusable.
     Depends on pip azure module 2.0.0 or above and azure-mgmt-compute 2.1.0 and above."
module: azure_rm_image
options:
  resource_group_name:
    description:
      - "The resource group name to use or create to host the deployed template"
    required: true
  name:
    description:
      - "The name of the image being created."
    required: True
  vm_name:
    description:
      - "The name of the VM within the resource group to capture. Required when state=present."
    required: false
  location:
    description:
      - "The location where the image should be stored. Should be within the resource group."
    default: The location of the resource group
    required: false
  state:
    description:
      - "The desired state of the image"
    default: present
    choices: present, absent
    required: false
  tags:
    description:
        - Tags to assign to the image.
    required: false

short_description: "Capture Azure Virtual Machine Images"
version_added: "2.9"

'''

EXAMPLES = '''
- name: Capture image
  hosts: 127.0.0.1
  connection: local

  tasks:
    - name: Capture image
      azure_rm_image:
        subscription_id: "{{ subscription_id }}"
        resource_group_name: "{{ resource_group_name }}"
        client_id: "{{ secrets.client_id }}"
        tenant_id: "{{ tenant_id }}"
        client_secret: "{{ secrets.client_secret }}"
        vm_name: "{{ vm_name }}"
        name: "{{ vm-name }}-image"
        location: "{{ location }}"
        state: present

    - name: Delete image
      azure_rm_image:
        subscription_id: "{{ subscription_id }}"
        resource_group_name: "{{ resource_group_name }}"
        client_id: "{{ secrets.client_id }}"
        tenant_id: "{{ tenant_id }}"
        client_secret: "{{ secrets.client_secret }}"
        name: "{{ vm-name }}-image"
        location: "{{ location }}"
        state: absent
'''

from ansible.module_utils.azure_rm_common import AzureRMModuleBase

try:
    from msrestazure.azure_exceptions import CloudError
    from azure.mgmt.compute.models import Image
    from azure.mgmt.compute.models import SubResource
# from azure.mgmt.compute.models import VirtualMachineCaptureParameters
except:
    pass


class AzureRMImage(AzureRMModuleBase):
    def __init__(self):

        self.module_arg_spec = dict(
            resource_group=dict(
                type='str',
                required=True
            ),
            vm_name=dict(
                type='str',
                required=False
            ),
            name=dict(
                type='str',
                required=True
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

        required_if = [
            ('state', 'present', ['vm_name'])
        ]

        self.resource_group = None
        self.vm_name = None
        self.name = None
        self.state = None
        self.location = None

        self.results = dict(
            changed=False,
            ansible_facts=dict(azure_images=None)
        )

        super(AzureRMImage, self).__init__(
            derived_arg_spec=self.module_arg_spec,
            required_if=required_if,
            supports_check_mode=True,
            supports_tags=True)

    def exec_module(self, **kwargs):

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        try:
            resource_group = self.get_resource_group(self.resource_group)
        except CloudError:
            self.fail('resource group {} not found'.format(self.resource_group))
        if not self.location:
            self.location = resource_group.location
        if self.state == 'present':
            self.results = self.capture_image()
        elif self.state == 'absent':
            self.results = self.delete_image()
        return self.results

    def _list_images(self):
        try:
            images = self.compute_client.images
            image_list = images.list()  # (resource_group_name=self.resource_group, name=self.name)
        except CloudError:
            self.fail("No images found!")
        except Exception as e:
            self.fail("An exception occurred: {}".format(str(e)))

        named_images = []

        for image in image_list:
            image_info = dict(name=image.name,
                              location=image.location,
                              resource_group=image.id.split("/")[4],
                              managed=(not (image.storage_profile.os_disk.managed_disk is None))
                              )
            named_images.append(image_info)

        return named_images

    def capture_image(self):

        try:
            vms = self.compute_client.virtual_machines
            vms.get(resource_group_name=self.resource_group, vm_name=self.vm_name)
        except CloudError:
            self.fail("VM {} not found!".format(self.vm_name))
        except Exception as e:
            self.fail("An exception occurred: {}".format(str(e)))

        image_names = self._list_images()

        found = any(elem['name'] == self.name for elem in image_names)

        if not found:

            images = self.compute_client.images
            source_vm = vms.get(resource_group_name=self.resource_group, vm_name=self.vm_name).id
            params = Image(location=self.location, source_virtual_machine=SubResource(source_vm))
            if self.check_mode:
                return_data = dict(name=self.name,
                                   status="Succeeded",
                                   location=self.location,
                                   resource_group=self.resource_group,
                                   changed=True)
            else:
                vms.deallocate(self.resource_group, self.vm_name).wait()
                vms.generalize(self.resource_group, self.vm_name)
                operation = images.create_or_update(resource_group_name=self.resource_group,
                                                    image_name=self.name, parameters=params)
                operation.wait()
                result = operation.result()

                return_data = dict(name=result.name,
                                   status=result.provisioning_state,
                                   location=result.location,
                                   resource_group=self.resource_group,
                                   changed=True)
        else:
            return_data = dict(name=self.name,
                               status="Image already exists",
                               changed=False)

        return return_data

    def delete_image(self):

        changed = False
        status = "Not found"
        image_names = self._list_images()

        found = any(elem['name'] == self.name for elem in image_names)

        if found:
            if self.check_mode:
                status = "Succeeded"
                changed = "True"
            else:
                images = self.compute_client.images
                operation = images.delete(resource_group_name=self.resource_group, name=self.name)

                operation.wait()
                result = operation.result()
                status = result.status

                if status == "Succeeded":
                    changed = True

        return dict(changed=changed,
                    status=status)


def main():
    AzureRMImage()


if __name__ == '__main__':
    main()
