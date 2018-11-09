#!/usr/bin/env python

from odoo import models, fields, api, _
import os
import base64
from .sharepoint import SharePointIntegration
from odoo.exceptions import UserError, ValidationError
from openerp.osv import osv

# import platform

root_path = os.path.dirname(os.path.abspath(__file__))


class sharepointcredentials(models.Model):
    _name = 'sharepoint.credentials'
    name = fields.Char(string='SharePoint Account Name', required=True)
    url = fields.Char(string='Root URL',required=True)
    email = fields.Char(string='Email', required=True)
    pass_word = fields.Char(string='Password', required=True)
    site_name = fields.Char(string='Site Name')
    document_name = fields.Char(string='Document Library Name')



    @api.one
    def test_connection(self):

        sp_obj = SharePointIntegration(self.url, self.email, self.pass_word)
        connection_flag = sp_obj.check_connection()
        if connection_flag:
            raise osv.except_osv(_("Success!"), _(" Connection Successful !"))
        else:
            raise osv.except_osv(_("Failure!"), _(" Connection Failed !"))


class sharepointlinks(models.Model):

    _name = 'documents.links'

    order_id = fields.Many2one('res.partner', string='Partner Reference', required=True, ondelete='cascade', index=True, copy=False)

    customer_name = fields.Char('Customer Name')
    name = fields.Char('Document Name')
    document_link = fields.Char('Document Link')

    status = fields.Char(string='Status')

    @api.multi
    def download_file_form_doc_link_sharepoint(self):
        customer_id = self.order_id

        if not customer_id.user_name_sharepoint:
            raise ValidationError(_('SharePoint account is missing'))

        if not self.document_link:
            raise ValidationError(_('SharePoint document link is missing'))


        document_name = self.name
        document_link_url = self.document_link

        sharepoint_email = customer_id.user_name_sharepoint.email
        sharepoint_url = customer_id.user_name_sharepoint.url
        sharepoint_pwd = customer_id.user_name_sharepoint.pass_word
        sharepoint_site_name = customer_id.user_name_sharepoint.site_name
        sharepoint_document_name = customer_id.user_name_sharepoint.document_name
        if not sharepoint_document_name:
            sharepoint_document_name = 'Documents'
        if sharepoint_site_name:
            sharepoint_site_name = sharepoint_site_name.replace(" ", "")

            sharepoint_site_name = 'sites/' + sharepoint_site_name + '/'

        if sharepoint_email and sharepoint_url and sharepoint_pwd:
            if self._uid == customer_id.user_name_sharepoint.create_uid.id:
                sp_obj = SharePointIntegration(sharepoint_url, sharepoint_email, sharepoint_pwd)
                connection_flag = sp_obj.check_connection()
                if connection_flag:

                    upload_file_names = []
                    for each in customer_id.downloaded_file_data_sharepoint:
                        upload_file_names.append(each.name)
                    directory_path = os.path.join(root_path, "files")
                    if not os.path.isdir(directory_path):
                        os.mkdir(directory_path)



                    sp_saved_files = sp_obj.get_file_list(sharepoint_site_name, sharepoint_document_name, self.customer_name)

                    if sp_saved_files:
                        is_list = isinstance(sp_saved_files, list)
                        if is_list:
                            # for old_file in sp_saved_files:
                            if document_name in sp_saved_files:
                                old_file = document_name
                                if old_file not in upload_file_names:
                                    print ("coming in old file check")
                                    file_path = os.path.join(directory_path, old_file)
                                    download_status = sp_obj.download_file_from_link(sharepoint_site_name,
                                                                                     sharepoint_document_name, old_file,
                                                                                     self.customer_name,
                                                                                     document_link_url,
                                                                                     file_path)
                                    if download_status:
                                        with open(file_path, "rb") as open_file:
                                            encoded_string = base64.b64encode(open_file.read())
                                        partner_id = customer_id.id
                                        # partner_id = self.id
                                        values = {'name': old_file,
                                                  'type': 'binary',
                                                  'res_id': partner_id,
                                                  'res_model': 'res.partner',
                                                  'partner_id': partner_id,
                                                  'datas': encoded_string,
                                                  'index_content': 'image',
                                                  'datas_fname': old_file,
                                                  }
                                        attach_id = self.env['ir.attachment'].create(values)
                                        self.env.cr.execute(
                                            """ insert into downloaded_ir_attachments_rel values (%s,%s) """ % (
                                                partner_id, attach_id.id))
                                        os.remove(file_path)
                                        self.status = 'Downloaded'
                            else:
                                raise ValidationError(_('%s is not available at SharePoint.' % (document_name)))
                        else:
                            raise ValidationError(_(sp_saved_files))
                    else:
                        raise ValidationError(_('No file found'))

                else:
                    raise ValidationError(_('Connection Failed! Please check your SharePoint credentials.'))

            else:
                raise ValidationError(_('Authentication Failed! Please verify your SharePoint account.'))

        else:
            raise ValidationError(_('Connection Failed!SharePoint credentials are missing.'))


class sharepointupload(models.Model):

    _inherit = 'res.partner'

    upload_file_data_sharepoint = fields.Many2many('ir.attachment', 'sharepoint_ir_attachments_rel', 'sharepoint_id', 'attachment_id', 'Attachments')
    downloaded_file_data_sharepoint = fields.Many2many('ir.attachment', 'downloaded_ir_attachments_rel', 'downloaded_id', 'attachment_id', 'Attachments')
    user_name_sharepoint = fields.Many2one('sharepoint.credentials', string='SharePoint Account')

    sharepoint_document_link = fields.Many2one('documents.links', string='SharePoint document link')

    download_type = fields.Selection([('file', 'File'), ('link', 'Link')], string='Download Type', default='file')

    # order_line = fields.One2many('documents.links', 'order_id', string='Documents links', copy=True)
    order_line = fields.One2many('documents.links', 'order_id', copy=True)

    @api.multi
    def upload_doc_sharepoint(self):

        if not self.upload_file_data_sharepoint:
            raise ValidationError(_('SharePoint attchments are missing'))

        if not self.user_name_sharepoint:
            raise ValidationError(_('SharePoint account is missing'))

        sharepoint_email = self.user_name_sharepoint.email
        sharepoint_url = self.user_name_sharepoint.url
        sharepoint_pwd = self.user_name_sharepoint.pass_word
        sharepoint_site_name = self.user_name_sharepoint.site_name
        sharepoint_document_name = self.user_name_sharepoint.document_name
        if not sharepoint_document_name:
            sharepoint_document_name = 'Documents'
        if sharepoint_site_name:
            # print 'hereeeeeeeeeeee'
            # print sharepoint_site_name
            # sharepoint_site_name = self.get_site_name(sharepoint_site_name)

            # sharepoint_site_name = sharepoint_site_name.replace(" ", "")
            sharepoint_site_name = 'sites/("' + sharepoint_site_name + '")'

            # print sharepoint_site_name

        if sharepoint_email and sharepoint_url and sharepoint_pwd:
            sp_obj = SharePointIntegration(sharepoint_url, sharepoint_email, sharepoint_pwd)
            connection_flag = sp_obj.check_connection()
            if connection_flag:
                if self._uid == self.user_name_sharepoint.create_uid.id:
                    check_customer_folder = sp_obj.get_folder_list(sharepoint_site_name, sharepoint_document_name)
                    # print "check_customer_folder"
                    # print check_customer_folder
                    if check_customer_folder:
                        is_list = isinstance(check_customer_folder, list)
                        if is_list:
                            upload_file_names = []
                            for each in self.upload_file_data_sharepoint:
                                upload_file_names.append(each.name)

                            if 'Customer' not in check_customer_folder:
                                out_put_flag = sp_obj.create_customer_folder(sharepoint_site_name,
                                                                             sharepoint_document_name, "Customer")
                                if not out_put_flag:
                                    raise ValidationError(_('Folder Error! Unable to create customer folder'))

                            out_put_flag = sp_obj.create_folder(sharepoint_site_name, sharepoint_document_name,
                                                                self.name)
                            if not out_put_flag:
                                raise ValidationError(_('Folder Error! Unable to create %s folder' % (self.name)))

                            ## sp_saved_files = sp_obj.get_file_list(sharepoint_site_name, sharepoint_document_name,
                            ##                                       self.name)
                            ## is_files_list = isinstance(sp_saved_files, list)
                            ## if is_files_list:
                            ##     for old_file in sp_saved_files:
                            ##         if old_file not in upload_file_names:
                            ##             sp_obj.delete_file(sharepoint_site_name, sharepoint_document_name, old_file,
                            ##                                self.name)

                            for each in self.upload_file_data_sharepoint:
                                attach_file_name = each.name
                                attach_file_data = each.sudo().read(['datas_fname', 'datas'])
                                directory_path = os.path.join(root_path, "files")
                                if not os.path.isdir(directory_path):
                                    os.mkdir(directory_path)
                                file_path = os.path.join("files", attach_file_name)
                                complete_path = os.path.join(root_path, file_path)
                                with open(complete_path, "wb") as text_file:
                                    text_file.write(base64.b64decode(attach_file_data[0]['datas']))
                                out_put_flag = sp_obj.create_file(sharepoint_site_name, sharepoint_document_name,
                                                                  complete_path, self.name, overwrite=True)
                                if not out_put_flag:
                                    raise ValidationError(_('File Error! Unable to create %s file.' % (complete_path)))
                                os.remove(complete_path)

                                downloadable_link = sp_obj.download_file_link(sharepoint_site_name,
                                                                                  sharepoint_document_name, attach_file_name,
                                                                                  self.name, file_path)

                                ### editing ###
                                ### print "downloadable_link during upload"
                                if downloadable_link:
                                    values = {'customer_name': self.name,
                                              'name': attach_file_name,
                                              'document_link': downloadable_link,
                                              'order_id': self.id,
                                              }
                                    attach_id = self.env['documents.links'].create(values)
                                ### end editing ###

                            # print "comin in query test"
                            Attachment = self.env['ir.attachment']
                            cr = self._cr

                            query = "SELECT attachment_id FROM sharepoint_ir_attachments_rel WHERE sharepoint_id="+str(self.id)+""

                            cr.execute(query)
                            attachments = Attachment.browse([row[0] for row in cr.fetchall()])
                            if attachments:
                                # print "attachments"
                                # print attachments
                                attachments.unlink()

                        else:
                            raise ValidationError(_(check_customer_folder))
                    else:
                        raise ValidationError(_('Site Error! Please check your SharePoint site'))

                else:
                    raise ValidationError(_('Authentication Failed! Please verify your SharePoint account.'))
            else:
                if self.upload_file_data_sharepoint:
                    raise ValidationError(_('Connection Failed! Please check SharePoint credentials.'))
        else:
            if self.upload_file_data_sharepoint:
                raise ValidationError(_('Connection Failed! SharePoint credentials are missing.'))

    @api.multi
    def download_docs_links_sharepoint(self):

        if not self.user_name_sharepoint:
            raise ValidationError(_('SharePoint account is missing'))

        sharepoint_email = self.user_name_sharepoint.email
        sharepoint_url = self.user_name_sharepoint.url
        sharepoint_pwd = self.user_name_sharepoint.pass_word
        sharepoint_site_name = self.user_name_sharepoint.site_name
        sharepoint_document_name = self.user_name_sharepoint.document_name
        if not sharepoint_document_name:
            sharepoint_document_name = 'Documents'
        if sharepoint_site_name:
            sharepoint_site_name = sharepoint_site_name.replace(" ", "")

            sharepoint_site_name = 'sites/' + sharepoint_site_name + '/'

        if sharepoint_email and sharepoint_url and sharepoint_pwd:
            if self._uid == self.user_name_sharepoint.create_uid.id:
                sp_obj = SharePointIntegration(sharepoint_url, sharepoint_email, sharepoint_pwd)
                connection_flag = sp_obj.check_connection()
                if connection_flag:

                    # upload_file_names = []
                    # for each in self.upload_file_data_sharepoint:
                    #     upload_file_names.append(each.name)

                    downloaded_links_file_names = []
                    customer_doc_objects = self.env['documents.links'].search([('customer_name', '=', self.name)])
                    if customer_doc_objects:
                        for each in customer_doc_objects:
                            doc_object = self.env['documents.links'].browse(each.id)
                            if doc_object:
                                doc_name = doc_object.name
                                downloaded_links_file_names.append(doc_name)

                    directory_path = os.path.join(root_path, "files")
                    if not os.path.isdir(directory_path):
                        os.mkdir(directory_path)

                    sp_saved_files = sp_obj.get_file_list(sharepoint_site_name, sharepoint_document_name, self.name)
                    if sp_saved_files:
                        is_list = isinstance(sp_saved_files, list)
                        if is_list:
                            for old_file in sp_saved_files:
                                if (old_file not in downloaded_links_file_names):
                                    # print "coming in old file check"
                                    file_path = os.path.join(directory_path, old_file)
                                    downloadable_link = sp_obj.download_file_link(sharepoint_site_name,
                                                                           sharepoint_document_name, old_file,
                                                                           self.name, file_path)
                                    if downloadable_link:

                                        values = {'customer_name': self.name,
                                                  'name': old_file,
                                                  'document_link': downloadable_link,
                                                  'order_id': self.id,
                                                  }
                                        attach_id = self.env['documents.links'].create(values)

                        else:
                            raise ValidationError(_(sp_saved_files))
                    else:
                        raise ValidationError(_('No file found'))
                else:
                    raise ValidationError(_('Connection Failed! Please check your SharePoint credentials.'))

            else:
                raise ValidationError(_('Authentication Failed! Please verify your SharePoint account.'))

        else:
            raise ValidationError(_('Connection Failed!SharePoint credentials are missing.'))


