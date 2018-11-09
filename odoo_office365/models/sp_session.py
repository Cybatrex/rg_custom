import os
import re
import requests
import xml.etree.ElementTree as et
import pickle
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError



# XML namespace URLs
xmlns = {
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"
}


class SharePointSession(requests.Session):
    def __init__(self, site=None,user_name='',pass_word=''):
        super(SharePointSession,self).__init__()
        self.username = user_name
        self.password = pass_word

        if site is not None:
            self.site = re.sub(r"^https?://", "", site)
            self.expire = datetime.now()


            if self.connection():
                self.refresh()
                self.headers.update({
                    "Accept": "application/json; odata=verbose",
                    "Content-type": "application/json; odata=verbose"
                })


    def connection(self):

        with open(os.path.join(os.path.dirname(__file__), "sp_template.xml"), "r") as file:
            saml = file.read()

        password = self.password
        saml = saml.format(username=self.username,
                           password=password,
                           site=self.site)


        # Request security token from Microsoft Online
        response = requests.post("https://login.microsoftonline.com/extSTS.srf", data=saml)
        # Parse and extract token from returned XML
        try:
            root = et.fromstring(response.text)
            token = root.find(".//{" + xmlns["wsse"] + "}BinarySecurityToken").text
        except Exception as err:
            connect_fail_string = "Token request failed. Check your username and password\n"

            return

        # Request access token from sharepoint site

        try:
            response = requests.post("https://" + self.site + "/_forms/default.aspx?wa=wsignin1.0",
                                     data=token, headers={"Host": self.site})
        except Exception as err:
            raise ValidationError('Max retries for SharePoint account have been exceeded, please check your SharePoint trial periad!')

        # Create access cookie from returned headers
        cookie = self._buildcookie(response.cookies)
        # Verify access by requesting page
        response = requests.get("https://" + self.site + "/_api/web", headers={"Cookie": cookie})

        if response.status_code == requests.codes.ok:
            self.headers.update({"Cookie": cookie})
            self.cookie = cookie

            # self._logger.debug("Authentication successful")
            return True
        # else:
            # self._logger.error("Authentication failed")




    # Check and refresh site's request
    def refresh(self):
        # Check for expired date
        if self.expire <= datetime.now():
            # Request site context info from SharePoint site
            response = requests.post("https://" + self.site + "/_api/contextinfo",
                                     data="", headers={"Cookie": self.cookie})

            try:
                root = et.fromstring(response.text)
                self.digest = root.find(".//{" + xmlns["d"] + "}FormDigestValue").text
                timeout = int(root.find(".//{" + xmlns["d"] + "}FormDigestTimeoutSeconds").text)
                self.headers.update({"Cookie": self._buildcookie(response.cookies)})
            except Exception as err:
                # self._logger.error(err)
                return
            # Calculate digest expiry time
            self.expire = datetime.now() + timedelta(seconds=timeout)

        return self.digest

    def post(self, url,data='', *args, **kwargs):
        if "headers" not in kwargs.keys():
            kwargs["headers"] = {}
        kwargs["headers"]["Authorization"] = "Bearer " + self.refresh()
        return super(SharePointSession,self).post(url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        if "headers" not in kwargs.keys():
            kwargs["headers"] = {}
        kwargs["headers"]["Authorization"] = "Bearer " + self.refresh()
        return super(SharePointSession,self).delete(url, **kwargs)

    def getfile(self, url, *args, **kwargs):
        # Extract file name from request URL if not provided as keyword argument


        filename = kwargs.pop("filename", re.search("[^\/]+$", url).group(0))
        kwargs["stream"] = True
        # Request file in stream mode
        response = self.get(url, *args, **kwargs)

        # Save to output file
        if response.status_code == requests.codes.ok:
            try:
                with open(filename, "wb") as file:
                    for chunk in response:
                        file.write(chunk)
                file.close()
            except Exception as err:
                raise ValidationError('Error on file saving on the following path: \n'+str(filename))
                
                
        return response

    # Create session cookie from response cookie dictionary
    def _buildcookie(self, cookies):
        return "rtFa=" + cookies["rtFa"] + "; FedAuth=" + cookies["FedAuth"]
