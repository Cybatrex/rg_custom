import logging
from .sp_session import SharePointSession
import ntpath
import json


class SharePointIntegration(object):

    def __init__(self,url,email,password):
        self._logger = logging.getLogger('CMIS Wrapper')

        self.headers = {"Accept": "application/atom+xml"}
        if url[-1] == '/':
            url = url[0:-1]
        self.root_url = url
        self.sharepoint = SharePointSession(self.root_url, email, password)

    def create_file(self, site_name, document_folder_name, file_with_path,folder_name,overwrite=False):

        try:
            if overwrite:
                overwrite = "true"
            else:
                overwrite ="false"
            storing_file_name = ntpath.basename(file_with_path)

            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name +"')/rootfolder/folders('Customer')"
            file_url = url + customer_folder_path + "/folders('" + folder_name + "')/files/add(url='" + storing_file_name + "',overwrite="+ overwrite+")"

            file_content = open(file_with_path, 'rb')
            resp = self.sharepoint.post(file_url,data = file_content,headers=self.headers)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def create_folder(self, site_name, document_folder_name, folder_name):
        try:
            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name +"')/rootfolder/folders('Customer')"
            folder_url = url + customer_folder_path +"/folders/add(url='" + folder_name +"')"

            resp = self.sharepoint.post(folder_url, headers=self.headers)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def delete_file(self, site_name, document_folder_name,file_name,folder_name):

        try:

            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url
            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name + "')/rootfolder/folders('Customer')"
            delete_file_url = url + customer_folder_path + "/folders('"+ folder_name +"')/files('"+ file_name+"')"

            resp = self.sharepoint.delete(delete_file_url,headers=self.headers)
            if resp.status_code == 200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def delete_folder(self, site_name, document_folder_name, folder_name):
        try:
            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name + "')/rootfolder/folders('Customer')"

            delete_folder_url = url + customer_folder_path + "/folders('" + folder_name + "')"

            resp = self.sharepoint.delete(delete_folder_url, headers=self.headers)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def download_file(self,site_name,document_folder_name,file_name,folder_name,save_to_file_path='temp.txt'):
        try:
            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name +"')/rootfolder/folders('Customer')"

            download_file_url = url + customer_folder_path + "/folders('"+ folder_name +"')/files('"+ file_name+"')/$value"
            # print "download_file_url"
            # print download_file_url

            resp = self.sharepoint.getfile(download_file_url,filename = save_to_file_path)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def download_file_link(self,site_name,document_folder_name,file_name,folder_name,save_to_file_path='temp.txt'):
        try:
            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name +"')/rootfolder/folders('Customer')"

            download_file_url = url + customer_folder_path + "/folders('"+ folder_name +"')/files('"+ file_name+"')/$value"
            # print "download_file_url"
            # print download_file_url

            return download_file_url
        except Exception as err:
            self._logger.error(err)
            return False

    def download_file_from_link(self,site_name,document_folder_name,file_name,folder_name,document_link_url,save_to_file_path='temp.txt'):
        try:

            download_file_url = document_link_url
            # print "sharepoint_document_link"
            # print download_file_url

            resp = self.sharepoint.getfile(download_file_url,filename = save_to_file_path)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False

    def get_file_list(self,site_name,document_folder_name,folder_name):
        try:
            file_name_array = []
            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            customer_folder_path = "/_api/web/Lists/getbytitle('" + document_folder_name +"')/rootfolder/folders('Customer')"
            file_list_url = url + customer_folder_path + "/folders('" + folder_name + "')/Files"

            resp = self.sharepoint.get(file_list_url)
            json_loads = json.loads(resp.text)
            if 'error' in json_loads:
                error_msg = json_loads['error']['message']['value']
                return error_msg
            result_files = json_loads['d']['results']
            for each in result_files:
                file_name = each['Name']
                file_name_array.append(file_name)
            return file_name_array
        except Exception as err:
            self._logger.error(err)
            return False




    def get_folder_list(self,site_name,document_folder_name):
        # print 'in get folder'
        # print site_name
        # print document_folder_name

        try:
            folder_name_array = []
            document_repository_path = "/_api/web/Lists/getbytitle('" + document_folder_name + "')/rootfolder"

            if site_name:
                url = self.root_url + '/' + site_name

            else:
                url = self.root_url

            folder_request_url = url + document_repository_path + "/folders/"

            # print folder_request_url
            resp = self.sharepoint.get(folder_request_url)
            # print resp
            json_loads = json.loads(resp.text)

            if 'error' in json_loads:
                error_msg = json_loads['error']['message']['value']
                return error_msg

            result_files = json_loads['d']['results']
            for each in result_files:
                file_name = each['Name']
                folder_name_array.append(file_name)
            return folder_name_array
        except Exception as err:
            self._logger.error(err)
            return False


    def check_connection(self):
        connection_flag = self.sharepoint.connection()
        if connection_flag==None:
            connection_flag=False
        return connection_flag

    def create_customer_folder(self,site_name,document_folder_name,root_folder_name):
        try:
            if site_name:
                url = self.root_url + '/' + site_name
            else:
                url = self.root_url

            document_repository_path = "/_api/web/Lists/getbytitle('" + document_folder_name + "')/rootfolder"
            customer_folder_request_url = url + document_repository_path + "/folders/add(url='" + root_folder_name +"')"
            resp = self.sharepoint.post(customer_folder_request_url, headers=self.headers)
            if resp.status_code==200:
                return True
            else:
                return False
        except Exception as err:
            self._logger.error(err)
            return False
