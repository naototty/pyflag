# ******************************************************
# Copyright 2004: Commonwealth of Australia.
#
# Michael Cohen <scudette@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.87-pre1 Date: Thu Jun 12 00:48:38 EST 2008$
# ******************************************************
#
# * This program is free software; you can redistribute it and/or
# * modify it under the terms of the GNU General Public License
# * as published by the Free Software Foundation; either version 2
# * of the License, or (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# ******************************************************
""" This module is designed to extract messages from live.com (the new
name for hotmail).

The reason this is needed is that most modern web mail applications
use so much javascript its impossible to make sense of the html
objects directly - they are not simple pages any more. This module
tries to extract certain pieces of information from the html object
specifically oriented towards the live.com/hotmail service.

How this works:

1) We only target inodes with a type of html as well as the regex
'<title>\s+Windows Live' in the top.

InboxLight pages (pages showing a view of the inbox or another mail
folder)

2) We obtain the list of folders by doing some dom navigation (find li
with class=FolderItemNormal, get the a below it and extract the
FolderID, get the span below that and get the name of the mail
box. This gives us a mapping between folder id and mailbox name).

3) Extract all the messages using some more DOM stuff:
  - Locate a table with class InboxTable, iterate over its rows

  - for each row, the 5th td is the to field. The mailbox can be found
  from the a tag there.

  - The subject is the 6th field. Date is the 7th field. Size is the
  8th field.

EditMessageLight - This page is what the user receives when they want
to edit a new message.

3) Search for a table with class ComposeHeader, iterate over its rows
   - For each row extract the fields from the id attributes:

     - From tr - find an option tag with selected attribute

     - To tr, Cc tr, Bcc tr, Subject tr - find an input tag and
     extract the value attribute

     - To find the actual context of the message search for script
     tags, with a regex:
     document.getElementById\(\"fEditArea\"\).innerHTML='([^']+)' The
     result needs to be unescaped suitably.

4) When EditMessageLight is called it has a form which submits into
itself. To get the post values look at the http_parameters table for
that HTTP object id.
"""
import pyflag.FlagFramework as FlagFramework
from pyflag.ColumnTypes import StringType, TimestampType, AFF4URN, IntegerType, PacketType
import FileFormats.HTML as HTML
import FileFormats.Javascript as Javascript
import pyflag.DB as DB
import pyflag.Scanner as Scanner
import pyflag.Reports as Reports
import pyflag.FileSystem as FileSystem
import re,cgi,pdb
import pyflag.pyflaglog as pyflaglog
import textwrap
import pyflag.HTMLUI as HTMLUI
import pyflag.Registry as Registry
import pyflag.Graph as Graph
import pyflag.Time as Time
import pyflag.CacheManager as CacheManager


Live20Style = """.SortSearchContainer{z-index:3;background-color:#BBD8FB;background-position:left bottom;background-repeat:repeat-x;height:2.15em;}
.Managed .SortSearchContainer{position:absolute;top:0px;left:0em;right:0em;}
.IE_M6 .Managed .SortSearchContainer{anchor:horizontal;behavior:expression(Anchor(this));width:100%;}
.SortSearchContainerHidden{z-index:-1;display:none;}
.SortSearchContainer .Toolbar{border:none;}
.SortSearchContainer .ToolbarItem UL{padding:2px;}
.SortSearchContainer .ToolbarItem UL A{padding:4px;}
.c_m .GroupHeading{border-top-width:1px;border-top-style:solid;border-top-color:#ccc;padding-top:4px;}
.ToolbarItemCheckbox INPUT{margin:0px;}
HTML.IE_M7 .ToolbarItemCheckbox INPUT{margin-left:3px;}
HTML.IE_M6 .ToolbarItemCheckbox INPUT{margin-left:3px;margin-right:3px;}
.SortSearchContainer .ToolbarItemCheckbox{padding-left:10px;padding-top:0.4em;}
.IE .SortSearchContainer .ToolbarItemCheckbox{padding-left:7px;}
.SortSearchContainer .ToolbarItemFirst .c_ml{padding-left:10px;}
.MessageListSplitPane{margin-top:2px;top:2.15em;z-index:2;}
.Managed .MessageListSplitPane{position:absolute;display:block;left:0em;overflow:hidden;}
.MessageListSplitPaneFull{bottom:0px;right:0px;}
.BottomUnmanaged .MessageListSplitPaneFull{margin-top:0px;position:static;}
.IE_M6 .MessageListSplitPaneFull{anchor:all;behavior:expression(Anchor(this));width:100%;height:100%;}
.IE_M6 .BottomUnmanaged .MessageListSplitPaneFull, .IE_M6 .BottomUnmanaged .ReadingPaneSplitPaneFull{width:auto;}
.MessageListSplitPaneHidden{z-index:-1;display:none;}
.MessageListItems{background-color:#ffffff;}
.Managed .MessageListItems{position:absolute;top:0px;bottom:25px;left:0px;right:0px;overflow-y:auto;overflow-x:hidden;}
.IE_M6 .Managed .MessageListItems{anchor:all;behavior:expression(Anchor(this));width:100%;height:80%;}
.PaginationContainer{background-color:#F3F7FD;height:1.8em;}
.Managed .PaginationContainer{position:absolute;bottom:0px;left:0px;right:0px;}
.IE_M6 .Managed .PaginationContainer{anchor:horizontal;behavior:expression(Anchor(this));width:100%;}
.SplitterBar{position:absolute;}
.IE_M6 .SplitterBar{overflow:hidden;background-color:white;}
.SplitterBarHidden{z-index:-1;display:none;}
.ReadingPaneSplitPane{border:1px solid #ccc;z-index:0;display:block;}
.Managed .ReadingPaneSplitPane{position:absolute;bottom:0em;right:0em;}
.ReadingPaneSplitPaneFull{top:0px;left:0px;}
.BottomUnmanaged .ReadingPaneSplitPaneFull{margin-top:0px;position:static;}
.IE_M6 .ReadingPaneSplitPaneFull{anchor:all;behavior:expression(Anchor(this));width:100%;height:100%;}
.ReadingPaneSplitPaneHidden{z-index:-1;display:none;}
.ReadingPaneSplitPaneFull .FullViewButton{display:none;}
.ActionBar{background-color:#ffffff;}
.Managed .ActionBar{position:absolute;top:0px;left:0px;right:0px;height:2.15em;}
.IE_M6 .ActionBar{anchor:horizontal;behavior:expression(Anchor(this));width:100%;}
.ReadingPaneContainer{margin-top:1px;background-color:#ffffff;}
.Managed .ReadingPaneContainer{position:absolute;top:2.15em;bottom:0px;left:0em;right:0px;overflow-y:auto;overflow-x:auto;}
.IE_M6 .Managed .ReadingPaneContainer{anchor:all;behavior:expression(Anchor(this));width:100%;height:80%;}
.ReadingPaneContainerNoActionBar{top:0px !important;}
.BottomUnmanaged .ReadMsgBody{overflow-x:hidden;}
.BottomUnmanaged .ReadingPaneContainer.ExpandMessage .ReadMsgBody{overflow-x:visible;}
.BottomUnmanaged .WithSkyscraper .ExpandMessageButton{display:block;}
.InboxTable{width:100%;table-layout:fixed;border-collapse:collapse;}
.IE .InboxTable{width:auto;}
.IE_M6 .InboxTable{position:relative;}
.InboxTable A{text-decoration:none;white-space:nowrap;}
.IE_M6 .InboxTable A{text-decoration:none !important;}
.InboxTable INPUT, .InboxTable IMG{border:none;margin:0px;padding:0px;}
.IE_M7 .InboxTable IMG{vertical-align:middle;}
.IE .InboxTable INPUT, .IE .ToolbarItemCheckbox INPUT{width:15px;}
.InboxTable TD{border-bottom-width:1px;border-bottom-style:solid;border-bottom-color:#f0f0f0;padding-top:1px;padding-bottom:1px;overflow:hidden;cursor:pointer;white-space:nowrap;}
.InboxTable .Ico, .InboxTable .Imp, .InboxTable .Att{padding-top:2px;padding-bottom:0px;}
.IE_M6 .InboxTable .Ico, .IE_M6 .InboxTable .Imp, .IE_M6 .InboxTable .Att{padding-left:4px;}
.InboxTable .Chk{padding-left:10px;padding-right:8px;}
.InboxTable .Frm{padding-left:12px;text-overflow:ellipsis;}
.InboxTable .Imp{padding-left:16px;}
.InboxTable .Att{padding-left:4px;}
.InboxTable .Sbj{padding-left:8px;text-overflow:ellipsis;}
.InboxTable .Dat, .InboxTable .Siz{padding-left:16px;padding-right:10px;text-align:right;color:#888;font-weight:normal !important;}
.InboxTable .CheckBoxCol{width:34px;}
.InboxTable .IconCol{width:17px;}
.InboxTable .FromCol{width:162px;}
.InboxTable .ImportanceCol{width:25px;}
.InboxTable .AttachmentCol{width:22px;}
.InboxTable .DateCol, .InboxTable .SizeCol{width:96px;}
.IE .InboxTable .CheckBoxCol{width:15px;}
.IE .InboxTable .IconCol{width:17px;}
.IE .InboxTable .FromCol{width:150px;}
.IE .InboxTable .ImportanceCol{width:9px;}
.IE .InboxTable .DateCol, .IE .InboxTable .SizeCol{width:80px;}
.PageNavigation{padding-right:8px;}
.PageNavigation UL{margin:0px;}
.PageNavigation LI{padding:4px 2px;height:100%;list-style:none;float:left;}
.PageNavigation LI A, .PageNavigation LI DIV{display:block;}
.PageNavigationPrev{margin-left:6px;}
.IE .PageNavigationPrev, .IE .PageNavigationNext{vertical-align:middle;}
.PageNavigationMsgRange{padding:4px 10px;float:left;}
.DragNDrop{position:absolute;z-index:1000;top:0px;left:0px;}
.rtl .DragNDrop{width:15em;}
.Firefox .DragNDrop, .Safari .DragNDrop{width:auto;}
.DragNDrop .Content{border:1px solid #ccc;padding:8px 8px 5px;position:relative;background-color:white;color:#444;z-index:2;white-space:nowrap;}
.App.Managed .MasterSplitter{cursor:col-resize;}
.ReadMsgContainer{padding:0px 12px;background-color:#FFFFFF;}
.ReadMsgHeader{padding-bottom:5px;height:auto !important;}
HTML.IE .ReadMsgHeader, HTML.IE .ReadMsgContainer{height:1%;}
.ReadMsgHeader TD{padding-right:4px;padding-bottom:2px;vertical-align:top;}
.ReadMsgHeaderCol1{color:#888;white-space:nowrap;}
.ReadMsgHeaderCol2{width:100%;}
.AttachmentContainer .AttachmentRow{padding-bottom:2px;}
.AttachmentContainer .AttachmentCount td{vertical-align:bottom;}
.AttachmentContainer .AttachmentCount .AttIcon{padding-bottom:3px;width:7px;}
.AttachmentContainer .AttachmentCount .ScanLogo{text-align:right;}
.AttachmentDownloadIframe{border:none;width:0px;height:0px;}
HTML.IE .AttachmentDownloadIframe, HTML.Firefox .AttachmentDownloadIframe{display:none;}
.ReadMsgHeader IMG{vertical-align:middle;}
.IE .ReadMsgHeader IMG{vertical-align:bottom;}
.ReadMsgSubject{padding:12px 0px 8px;font-size:1.46em;}
.ReadMsgHeader .SenderSafetyMsg{padding:0px 4px;}
.ReadMsgHeader .SenderSafetyLinks{padding:0px 8px;display:inline-block;}
.ReadMsgBody{padding:10px 0px;}
.PlainTextMessageBody PRE{white-space:normal;}
.MessageSelection{padding:8px 4px 6px;}
.MessageSelection H2{font-size:132%;font-weight:bold;color:#444444;}
.ReadMsgSafetyBar, .WideMessageBar{margin-top:8px;padding:3px 8px 5px;height:auto !important;}
.MessageLevel{vertical-align:bottom;}
.SafetyBarPri-high{background-color:#FFAEB9;}
.SafetyBarPri-medium, .WideMessageBar{background-color:#FFFFAE;}
.SafetyBarPri-low{background-color:#FFFFFF;}
.SafetyBarItem{padding:3px 4px;clear:both;}
.SafetyBarItem A, .WideMessageBar A{margin:0px 20px;display:inline-block;}
.SafetyBarItem A.FirstLink{margin-right:8px;}
.SafetyBarItem A.LastLink{margin-left:8px;}
.MeetingReqBar A{margin:4px 0px;padding:0px 8px;display:block;color:#000000;}
.MeetingReqBar A *{padding:4px 0px;vertical-align:middle;}
.ButtonList{padding-left:10px;padding-right:10px;background-color:#eceeee;}
.ButtonList UL{margin:0em;padding:0em;list-style-type:none;list-style-image:none;}
.ButtonList UL LI{margin:2px 0px;float:left;height:22px;}
.ButtonList LI A{border:1px solid transparent;text-decoration:none;position:relative;display:block;top:.25em;height:16px;width:16px;overflow:hidden;direction:ltr;outline:0em;}
.ButtonList LI A:hover{text-decoration:none;}
.ButtonList LI A.dropdown{color:#444;direction:inherit;width:90%;height:auto;}
.ButtonList LI A.dropdown .caption{display:block;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;width:85%;}
.ButtonList A.ImageIcon{top:.4em;}
.IE_M6 .ButtonList LI A{border:1px solid #eee;}
.ButtonList LI IMG{border-width:0px;position:relative;}
.ButtonList LI.Selected A{border:1px solid #83aada;background-color:#DDECFE;}
.Menu{position:absolute;top:0px;left:0px;overflow:visible;}
.Menu, .Menu DIV{min-width:15em;}
.IE_M6 .Menu, .rtl.IE_M7 .Menu{width:15em;}
.Menu .shadow{position:absolute;top:3px;left:3px;width:100%;height:100%;background-color:#000000;opacity:0.3;filter:alpha(opacity=30);}
.Menu UL{border:1px solid #ccc;margin:0px;padding:0px;position:relative;background-color:#FCFCFC;z-index:1;list-style-type:none;}
.Menu UL LI{margin:2px;padding:0px;}
.Menu UL LI.Divider{line-height:4px;display:block;height:4px;overflow:hidden;}
HTML.IE_M6 .Menu UL LI.Divider{height:auto;overflow:auto;}
.Menu UL LI.Divider DIV{border-width:0px 0px 1px;border-style:solid;border-color:#fcfcfc #fcfcfc #ccc;margin:2px;height:2px;overflow:hidden;position:relative;top:-2px;}
HTML.IE_M6 .Menu UL LI.Divider DIV{margin:auto;height:1px;position:static;left:auto;top:auto;}
.Menu .Disabled A{color:#BBB;}
.Menu .Selected A{border:1px solid #83aada;background-color:#DDECFE;}
.Menu A{border:1px solid #fcfcfc;padding:2px 5px 4px;color:#444 !important;white-space:nowrap;text-overflow:ellipsis;width:auto;display:block;position:relative;z-index:1;}
.IE_M6 .Menu A{height:100%;}
.Menu A:hover{border:1px solid #bbd8fb;background-color:#F3F7FD;text-decoration:none;}
"""

class HTMLStringType(StringType):
    """ A ColumnType which sanitises its input for HTML.
    We also fetch images etc from the db if available.
    """
    def xxxdisplay(self, value, row, result):
        parser = HTML.HTMLParser(tag_class = HTML.SanitizingTag)
        parser.feed(value)
        parser.close()

        return parser.root.innerHTML()

    def render_html(self, value, table_renderer):
        import plugins.TableRenderers.HTMLBundle as HTMLBundle

        parser = HTML.HTMLParser(tag_class = HTML.TextTag)

        parser.feed(value or '')
        parser.close()

        text = parser.root.innerHTML()

        ## Make sure its wrapped:
        ui = HTMLUI.HTMLUI(initial=True)
        ui.text(text, wrap ='full', font='typewriter')
        return ui.__str__()

    def display(self, value, row, result):
        parser = HTML.HTMLParser(tag_class = HTML.TextTag)
        parser.feed(value or '')
        parser.close()

        value = parser.root.innerHTML()

	result.text(value, wrap='full', font='typewriter')


class WebMailTable(FlagFramework.CaseTable):
    """ Table to store Web mail related information """
    name = 'webmail_messages'
    columns = [
        [ AFF4URN, {} ],
        [ StringType, dict(name="Service", column='service')],
        [ StringType, dict(name='Type', column='type')],
        [ HTMLStringType, dict(name='From', column='From')],
        [ StringType, dict(name='To', column='To')],
        [ StringType, dict(name='CC', column='CC')],
        [ StringType, dict(name='BCC', column='BCC')],
        [ StringType, dict(name='Subject', column='subject')],
        [ HTMLStringType, dict(name='Message', column='message', text=True)],
        [ StringType, dict(name='Identifier', column='message_id')],
        [ TimestampType, dict(name='Sent', column='sent')],
        ]

class WebMailAttachmentTable(FlagFramework.CaseTable):
    """ Table to store web mail attachment references """
    name = "webmail_attachments"
    columns = [
        [ AFF4URN, dict(name = "Message Inode") ],
        [ AFF4URN, dict(name = "Attachment", column="attachment") ],
        [ StringType, dict(name = "URL", column='url')],
        ]

import fnmatch

class HotmailScanner(Scanner.GenScanFactory):
    """ Detects Live.com/Hotmail web mail sessions """
    default = True
    depends = ['HTTPScanner']
    group = 'NetworkScanners'
    service = 'Hotmail Classic'
    message = ''

    def fixup_page(self, result, tag_class):
        """ Given the parse tree in root, fix up the page so it looks
        as close as possible to the way it should. We write the new
        page on outfd.
        """
        if not result.get('message'): return
        ## We have to inject the message into the edit area:
        edit_area = self.parser.root.find("div", {"class":"EditArea"}) or \
                    self.parser.root.find("div",{"id":"MsgContainer"}) or \
                    self.parser.root.find("textarea",{"id":"fMessageBody"})
        if edit_area:
            parser = HTML.HTMLParser(tag_class = tag_class)
            parser.feed(HTML.decode(result['message']))
            parser.close()
            result = parser.root.__str__()
            result = textwrap.fill(result)
            edit_area.prune()
            edit_area.add_child(result)
            edit_area.name = 'div'

        return self.parser.root.innerHTML()

    def scan(self, fd, factories, type, mime):
        if "HTML" in type:
            data = fd.read(1024)
            if not re.search("<title>\s+Windows Live", data): return

            ## Ok - we know its a Live page
            pyflaglog.log(pyflaglog.DEBUG,"Opening (%s) %s for Hotmail processing" % (fd.inode_id, fd.urn))
            self.parser =  HTML.HTMLParser(verbose=0)
            self.parser.feed(data.decode("utf8","ignore"))
            
            while len(data)>0:
                data = fd.read(1024)
                self.parser.feed(data.decode("utf8","ignore"))
                ## Get all the tokens
                while self.parser.next_token(True): pass

            ## Now we should be able to parse the data out:
            self.process_send_message(fd)
            self.process_editread(fd)
            self.process_readmessage(fd)
            self.process_mail_listing(fd)

    def process_mail_listing(self, fd):
        """ This looks for the listing in the mail box """
        table = self.parser.root.find("table",{"class":"ItemListContentTable InboxTable"})
        if not table: return False

        result = {'type': 'Listed', 'message': table}

        mail_box = self.parser.root.find("li", {"class":"FolderItemSelected"})
        if mail_box:
            mail_box = mail_box.find("span")
            if mail_box:
                result['From'] = mail_box.innerHTML()

        title = self.parser.root.find("a",{"class":"uxp_hdr_meLink"})
        if title:
            result['To'] = title.innerHTML()

        return self.insert_message(fd, result, inode_template = "l%s")


    def process_send_message(self,fd):
        ## Check to see if this is a POST request (i.e. mail is
        ## sent to the server):
        dbh = DB.DBO(self.case)
        dbh.execute("select `key`,`value` from http_parameters where inode_id = %r", fd.inode_id)
        query = dict([(r['key'].lower(),r['value']) for r in dbh])
        result = {'type':'Edit Sent' }
        for field, pattern in [('To','fto'),
                               ('From','ffrom'),
                               ('CC','fcc'),
                               ('BCC', 'fbcc'),
                               ('subject', 'fsubject'),
                               ('message', 'fmessagebody')]:
            if query.has_key(pattern):
                result[field] = query[pattern]

        if len(result.keys())>2:
            return self.insert_message(fd, result)
        else: return False

    def process_readmessage(self,fd):
        result = {'type': 'Read', 'message':''}
        root = self.parser.root

        tag = root.find('div', {'class':'ReadMsgContainer'})
        if not tag: return

        ## Find the subject:
        sbj = tag.find('td', {'class':'ReadMsgSubject'})
        if sbj: result['subject'] = HTML.decode_entity(sbj.innerHTML())

        ## Fill in all the other fields:
        context = None
        for td in tag.search('td'):
            data = td.innerHTML()
            if context:
                result[context] = HTML.decode_entity(data)
                context = None

            if data.lower().startswith('from:'):
                context = 'From'
            elif data.lower().startswith('to:'):
                context = 'To'
            elif data.lower().startswith('sent:'):
                context = 'sent'

        ## Now the message:
        ## On newer sites its injected using script:
        for s in root.search('script'):
            m=re.match("document\.getElementById\(\"MsgContainer\"\)\.innerHTML='([^']*)'", s.innerHTML())
            if m:
                result['message'] += HTML.decode_unicode(m.group(1).decode("string_escape"))
                break

        try:
            result['sent'] = Time.parse(result['sent'])
        except: pass

        return self.insert_message(fd, result)            

    def process_editread(self, fd):
        ## Find the ComposeHeader table:
        result = {'type':'Edit Read'}

        root = self.parser.root
        tag = root.find('table', {"class":'ComposeHeader'})
        if not tag:
            return

        ## Find the From:
        row = tag.find( 'select', dict(name = 'ffrom'))
        if row:
            option = row.find('option', dict(selected='.*'))
            result['From'] = HTML.decode_entity(option['value']) 

        for field, pattern in [('To','fto'),
                               ('CC','fcc'),
                               ('BCC', 'fbcc'),
                               ('subject', 'fsubject')]:
            tmp = tag.find('input', dict(name = pattern))
            if tmp:
                result[field] = HTML.decode_entity(tmp['value'])

        ## Now extract the content of the email:
        result['message'] = ''

        ## Sometimes the message is found in the EditArea div:
        div = root.find('div', dict(id='EditArea'))
        if div:
            result['message'] += div.innerHTML()

        ## On newer sites its injected using script:
        for s in root.search('script'):
            m=re.match("document\.getElementById\(\"fEditArea\"\)\.innerHTML='([^']*)'", s.innerHTML())
            if m:
                result['message'] += m.group(1).decode("string_escape")
                break

        return self.insert_message(fd, result)

    def insert_message(self, fd, result, inode_template="l%s"):
        try:
            assert(result['message'])
        except: return
        data = self.fixup_page(result, HTML.SanitizingTag)
        
        live_obj = CacheManager.AFF4_MANAGER.create_cache_data(
            fd.case, "/".join((fd.urn, "Message")),
            data.encode("utf8"),
            inherited = fd.urn)

        result['service'] = self.service
        live_obj.insert_to_table('webmail_messages', result)
        live_obj.close()

        return live_obj.inode_id

import pyflag.Magic as Magic

class Live20Magic(Magic.Magic):
    """ Identify Live 20 Messages """
    type = "Hotmail 2.0 AJAX"
    mime = "protocol/x-http-request"
    default_score = 100

    regex_rules = [
        ( "new HM.FppReturnPackage", (0,0)),
        ]
    
    samples = [
        ( 100, "new HM.FppReturnPackage(0,new HM.InboxUiData(null,null,\"\r\n\r\n\r\n<"),
        ]

class Live20Scanner(HotmailScanner):
    """ Parse Hotmail Web 2.0 Session """
    service = "Hotmail 2.0 AJAX"

    def scan(self, fd, factories, type, mime):
        if "Hotmail 2.0 AJAX" in type:
            pyflaglog.log(pyflaglog.DEBUG,"Opening %s for Hotmail AJAX processing" % fd.inode_id)
            js_parser = Javascript.JSParser()
            js_parser.parse_string(fd.read().decode("utf8"))

            ## Find the InboxUiData function in the AST
            f = js_parser.root.find("function", dict(name="InboxUiData"))
            if f:
                ## Im sure the args mean something but we just process
                ## them all the same - we can usually determine which
                ## arg goes where by the div classes.
                result = ''
                for child in f:
                    if child.name == 'string':
                        result += child.innerHTML()
                        
                self.process_string(fd, result)

    def process_string(self, fd, string):
        parser =  HTML.HTMLParser(verbose=0)
        parser.feed(string)
        parser.close()

        self.process_readmessage(fd, parser)
        self.process_listing(fd, parser)

    def process_listing(self, fd, parser):
        result = {'type':'Listing'}

        ## Find the currently highlighted mailbox
        mb = parser.root.find('li', {"class":"FolderItemSelected"})
        if mb:
            result['subject'] = mb.find('span').innerHTML()

        lst = parser.root.find("div", {"class":"MessageListItems"})
        if lst:
            result['message'] = lst.innerHTML()

        return self.insert_message(fd, result)        

    def fixup_page(self, result, tag_class):
        """ Its not really possible to represent AJAX communications
        properly, so we just write the message here.

        FIXME - It may be possible to render the page by inserting the
        message into a template created by other pages.
        """
        message = result.get('message','')
        return "<html>\r\n<head>\r\n<style>%s</style></head>\r\n<body>%s</body></html>" % (
            Live20Style,message)

    def process_readmessage(self, fd, parser):
        result = {'type': 'Read'}

        ## Find the subject
        sbj = parser.root.find('div', {'class':'ReadMsgSubject'})
        if sbj: result['subject'] = HTML.decode_entity(sbj.innerHTML())

        context = None
        for td in parser.root.search('td'):
            data = td.innerHTML()
            if context:
                result[context] = HTML.decode_entity(data)
                context = None

            if data.lower().startswith('from:'):
                context = 'From'
            elif data.lower().startswith('to:'):
                context = 'To'
            elif data.lower().startswith('sent:'):
                context = 'Sent'

        msg = parser.root.find('div', {'class':'ReadMsgContainer'})
        if msg:
            result['message'] = msg.innerHTML()


        ## Try to detect the message ID
        tag = parser.root.find('div', {'mid':'.'})
        if tag:
            result['message_id'] = tag['mid']

        try:
            result[context] = Time.parse(result[context])
        except: pass

        return self.insert_message(fd, result)

import os.path

class LiveAttachements(FlagFramework.EventHandler):
    def find_uploaded_attachments(self, dbh):
        dbh.execute("select * from http_parameters where `key`='fAttachments'")
        dbh2 = dbh.clone()
        for row in dbh:
            parent_inode_id = row['inode_id']
            ## Find all the attachments
            for line in row['value'].split("\x1b"):
                items = line.split("|")
                filename = items[2][36:]
                m = re.search("([^.]+)", filename)
                if m: filename = m.group(1)
                ## Try to locate the files as they got uploaded
                dbh2.execute("select * from http_parameters where `key`='Subject' and value=%r limit 1",
                             filename)
                row = dbh2.fetch()
                if row:
                    ## Is there an attachment?
                    dbh2.execute("select * from http_parameters where inode_id = %r and `key`='Attachment'",
                                 row['inode_id'])
                    row = dbh2.fetch()
                    if row:
                        attachment = row['indirect']

                        # Find the webmail message for this attachment
                        dbh2.execute("select * from webmail_messages where parent_inode_id = %r",
                                     parent_inode_id)
                        row = dbh2.fetch()
                        if row:
                            ## Check if there already is an entry in attachment table
                            dbh2.execute("select * from webmail_attachments where "
                                         "inode_id = %r and attachment = %r limit 1",
                                         (row['inode_id'], attachment))

                            if not dbh2.fetch():
                                dbh2.insert("webmail_attachments",
                                            inode_id = row['inode_id'],
                                            attachment =attachment)
    
    def periodic(self, dbh, case):
        """ A periodic handler to ensure that attachements are matched
        to their respective messages
        """
        try:
            self.find_uploaded_attachments(dbh)
        except: return
        dbh2 = dbh.clone()
        dbh3 = dbh.clone()
        dbh4 = dbh.clone()
        dbh3.check_index("webmail_messages","message_id")
        ## Iterate over all unique message ids
        dbh.execute("select message_id from webmail_messages group by message_id")
        for row in dbh:
            message_id = row['message_id']
            attachments = []
            ## For each message_id find direct download:
            dbh2.execute('select * from http where url like "%%GetAttachment%%messageId=%s%%"', message_id)
            for row in dbh2:
                inode_id = row['inode_id']
                if inode_id not in attachments:
                    attachments.append(inode_id)

            ## For each message id find possible SafeRedirect urls
            dbh2.execute('select http.inode_id, url from http_parameters join http on '
                         'http.inode_id = http_parameters.inode_id where  `key`="kr" and '
                         'value like "mid=%s%%" and url like "%%SafeRedirect%%"', message_id)
            for row2 in dbh2:
                ## Find out where they redirect to:
                dbh3.execute("select * from http_parameters where inode_id = %r and "
                             "(`key`='hm__qs' or `key`='hm__tg')", row2['inode_id'])
                tg = ''
                qs = ''
                for row3 in dbh3:
                    if row3['key'] == 'hm__tg': tg = row3['value']
                    elif row3['key'] == 'hm__qs': qs = row3['value']

                ## Try to locate the destination of the redirection
                dbh3.execute("select inode_id from http where url like '%s?%s%%'", (tg,qs))
                row3 = dbh3.fetch()
                if row3:
                    attachment = row3['inode_id']
                    if attachment not in attachments:
                        attachments.append(attachment)

            if attachments:
                for attachment in attachments:
                    ## Check all messages with the specific hotmail message id
                    dbh3.execute("select inode_id from webmail_messages where message_id = %r",
                                 message_id)
                    for row3 in dbh3:
                        ## Update the attachment table to contain the redirected URL.
                        dbh4.execute("select * from webmail_attachments where inode_id =%r and attachment=%r",
                                     (row3['inode_id'], attachment))
                        if not dbh4.fetch():
                            dbh4.insert("webmail_attachments",
                                        inode_id = row3['inode_id'],
                                        attachment = attachment)
        

class AttachmentColumn(AFF4URN):
    """ Displays the attachments related to the webmail message """
    def display(self, value, row, result):
        dbh = DB.DBO(self.case)
        fsfd = FileSystem.DBFS(self.case)
        dbh.execute("select file.inode_id as inode_id, name from file, webmail_attachments where webmail_attachments.inode_id = %r and file.inode_id = webmail_attachments.attachment", value)
        for row in dbh:
            tmp = result.__class__(result)

            try:
                fd = fsfd.open(inode_id=row['inode_id'])
                image = Graph.Thumbnailer(fd,100)
            except IOError:
                pass
            
            if image.height>0:
                tmp.image(image,width=image.width,height=image.height)
            else:
                tmp.image(image,width=image.width)

            link = result.__class__(result)
            name = row['name']
            if len(name) > 20: name = name[:20]+" ..."
            tmp.para(name)
            link.link(tmp, tooltip = row['name'],
                      pane = 'new',
                      target= FlagFramework.query_type(family = "Disk Forensics",
                                                       report = "ViewFile",
                                                       case = self.case,
                                                       mode = 'Summary',
                                                       inode_id = row['inode_id']))
            result.row(link)

class WebMailMessages(Reports.CaseTableReports):
    """
    Browse WebMail messages.
    --------------------------------

    This allows the results from the various webmail scanners to be viewed.

    """
    name = "Browse WebMail Messages"
    family = "Network Forensics"
    columns = ['URN', 'AFF4VFS.Modified', 'From','To', 'Subject','Message','Type','Service']
    default_table = 'WebMailTable'
    
import textwrap

## A VFS File driver which formats a row in the db nicely:
class TableViewer(FileSystem.StringIOFile):
    """ A VFS driver to read rows from an SQL table.

    Format is 't%s:%s:%s:%s' % (table_name, column_name, value, column_to_retrieve (optional))

    e.g. twebmail_messages:id:2
    """
    specifier = 't'

    def __init__(self, case, fd, inode):
        parts = inode.split('|')
        ourinode = parts[-1][1:]
        self.size = 0
        self.inode =inode
        self.case = case
        self.column_to_retrieve = None
                
        try:
            self.table, self.id = ourinode.split(':')
            self.value = self.lookup_id()
        except ValueError:
            try:
                self.table, self.id, self.value = ourinode.split(':')
            except ValueError:
                self.table, self.id, self.value, self.column_to_retrieve = ourinode.split(':')

        FileSystem.StringIOFile.__init__(self, case, fd, inode)
        self.force_cache()

    def read(self, length = None):
        try:
            return FileSystem.StringIOFile.read(self, length)
        except IOError: pass

        dbh = DB.DBO(self.case)
        dbh.execute("select * from %s where `%s`=%r", (self.table, self.id, self.value))

        result = '<html><body>'
        dbh = DB.DBO(self.case)
        dbh.execute("select * from %s where `%s`=%r", (self.table, self.id, self.value))
        for row in dbh:
            if self.column_to_retrieve:
                return row[self.column_to_retrieve]

            result += ("<table border=1>\n")
            for k,v in row.items():
                result += "<tr><td>%s</td>" % k
                result += "<td>%s</td></tr>\n" % textwrap.fill(
                    cgi.escape("%s" % v) or "&nbsp;",
                    subsequent_indent = "<br>")
                
            result += "</table></body></html>"
        return result

class LiveMailViewer(FileSystem.StringIOFile):
    """ A VFS Driver to render a realistic view of a Yahoo mail
    message without allowing scripts to run.
    """
    specifier = 'l'

    def __init__(self, case, fd, inode):
        parts = inode.split('|')
        self.id = parts[-1][1:]
        self.case = case
        self.inode = inode
        self.inode_id = self.lookup_id()
        dbh = DB.DBO(self.case)
        dbh.execute("select * from webmail_messages where inode_id=%r", (self.inode_id))
        row = dbh.fetch()
        if not row: raise RuntimeError("No such message %s" % self.id)

        self.parent_inode_id = row['parent_inode_id']
        self.message = row['message'] or ""
        self.size = len(self.message)
        
        FileSystem.StringIOFile.__init__(self, case, fd, inode)
        self.force_cache()
        
    def read(self, length = None):
        try:
            return FileSystem.StringIOFile.read(self, length)
        except IOError: pass

        ## We must always return a byte string for reads (files are
        ## always bytestreams)
        return self.message.encode("utf8")

    def fixup_page(self, root, tag_class):
        ## We have to inject the message into the edit area:
        edit_area = root.find("div", {"class":"EditArea"}) or \
                    root.find("div",{"id":"MsgContainer"}) or \
                    root.find("textarea",{"id":"fMessageBody"})
        if edit_area:
            parser = HTML.HTMLParser(tag_class = tag_class)
            parser.feed(HTML.decode(self.message))
            #parser.feed(self.message)
            parser.close()
            result = parser.root.__str__()
            result = textwrap.fill(result)
            edit_area.prune()
            edit_area.add_child(result)
            edit_area.name = 'div'

    def stats(self, query,result):
        result.start_table(**{'class':'GeneralTable'})
        dbh = DB.DBO(self.case)
        columns = ["service","type","From","To","CC","BCC","sent","subject","message"]
        dbh.execute("select * from webmail_messages where `inode_id`=%r", self.lookup_id())
        row = dbh.fetch()
        
        dbh2 = DB.DBO(self.case)
        dbh2.execute("select * from inode where inode_id = %r", row['inode_id'])
        row2 = dbh2.fetch()
        result.row("Timestamp", row2['mtime'])

        for c in columns:
            if c=='message':
                ## Filter the message out here:
                parser = HTML.HTMLParser(tag_class = \
                                         FlagFramework.Curry(HTML.ResolvingHTMLTag,
                                                             case = self.case,
                                                             inode_id = row['parent_inode_id']))
                #parser = HTML.HTMLParser(tag_class = HTML.TextTag)
                parser.feed(HTML.decode(row[c] or ""))
                parser.close()
                #tmp = result.__class__(result)
                #tmp.text(parser.root.innerHTML(), font='typewriter', wrap='full')
                #row[c] = tmp
                r = parser.root.__str__()
                r = textwrap.fill(r)
                row[c] = r
                
            result.row(c, row[c])

        dbh.execute("select url from http where inode_id = %r", row['parent_inode_id'])
        row = dbh.fetch()
        if row:
            tmp = result.__class__(result)
            tmp.text(row['url'], font='typewriter', wrap='full')
            result.row("URL", tmp)

    def sanitize_page(self, tag_class):
        """ This produces a rendered version of the underlying page """
        ## Get the original HTML File:
        fsfd = FileSystem.DBFS(self.case)
        fd = fsfd.open(inode_id = self.parent_inode_id)
        #data = HTML.decode(fd.read())
        data = fd.read()
        ## FIXME - This is a hack which works because we always send a
        ## curried class down:
        try:
            tag_class.kwargs['inode_id'] = self.parent_inode_id
        except AttributeError: pass
        
        ## Make a parser:
        p = HTML.HTMLParser(tag_class = tag_class)
        p.feed(data)
        p.close()

        ## Allow us to fix the html page
        root = p.root
        self.fixup_page(root, tag_class)

        ## Add the timestamp to the title of the page - so when you
        ## print it out we can identify it:
        s = fsfd.istat(inode_id = self.parent_inode_id)
        title_tag = root.find("title")
        if title_tag:
            title_tag.children = [ "%s %s %s" % (title_tag.innerHTML(),
                                                 s['mtime'], s['inode']) ,]
        
        return root.innerHTML()        

    def html_export(self, tag_class):
        return self.sanitize_page(tag_class)

    def summary(self, query, result):
        page = self.sanitize_page(tag_class = \
                                  FlagFramework.Curry(HTML.ResolvingHTMLTag,
                                                      case = self.case,
                                                      inode_id = self.parent_inode_id))
        def frame_cb(query, result):
            def generator():
                yield page

            result.generator.content_type = 'text/html'
            result.generator.generator = generator()

        def print_cb(query, result):
            def generator():
                yield page
                #yield page.replace("</html","<script>window.print()</script></html")

            result.generator.content_type = 'text/html'
            result.generator.generator = generator()

        result.iframe(callback = frame_cb)
        result.toolbar(cb = print_cb, text="Print", icon="printer.png", pane='new')
        
## PreCanned reports
class AllWebMail(Reports.PreCannedCaseTableReports):
    report="Browse WebMail Messages"
    family="Network Forensics"
    args = {"order":0, "direction":1, "filter":"Type != Listed"}
    default_table = 'WebMailTable'
    description = "View all Webmail messages"
    name = "/Network Forensics/Web Applications/Webmail"
    columns = [ 'URN', 'From', 'To', 'Subject', 'Message', 'Service', 'Type' ]
    
## Unit tests:
import pyflag.pyflagsh as pyflagsh
import pyflag.tests as tests

class HotmailTests(tests.ScannerTest):
    """ Tests Hotmail Scanner """
    test_case = "PyFlagTestCase"
#    test_file = 'live.com.pcap.e01'
#    test_file = 'private/livecom.pcap'
    test_file = 'private/hotmail_test.pcap'
#    test_file = 'gmail.com.pcap.e01'
    
    def test01HotmailScanner(self):
        """ Test Hotmail Scanner """
        env = pyflagsh.environment(case=self.test_case)
        pyflagsh.shell_execv(env=env,
                             command="scan",
                             argv=["*",                   ## Inodes (All)
                                   "HotmailScanner", "Live20Scanner",
                                   ])                   ## List of Scanners

        dbh = DB.DBO(self.test_case)
        dbh.execute("select count(*) as c from webmail_messages")
        row = dbh.fetch()
        self.assert_(row['c'] > 0, "No hotmail messages were found")

if __name__ == '__main__':
    import sys
    import pyflag.conf
    config = pyflag.conf.ConfObject()

    config.parse_options()

    Registry.Init()

    ## Update the current webmail_messages to include message ids
    dbh = DB.DBO(sys.argv[1])
    dbh1 = dbh.clone()
    dbh.execute("select inode_id, parent_inode_id, message_id from webmail_messages")
    for row in dbh:
        if not row['message_id']:
            data = ''
            m=''
            dbh1.execute("select `key`,value from http_parameters where inode_id=%r and `key`='kr' limit 1",
                         row['parent_inode_id'])
            row1 = dbh1.fetch()
            if row1:
                data = row1['value']
                m = re.search('mid=([^&]+)', data)
                
            if not m:
                dbh1.execute("select `key`,value from http_parameters where inode_id=%r and `key`='d' limit 1",
                         row['parent_inode_id'])
                row1 = dbh1.fetch()
                if row1:
                    data = row1['value']
                    m = re.search('\\{\\"([^\\"]+)\\"', data)

            if m:
                dbh1.execute("update webmail_messages set message_id = %r where inode_id = %r",
                             (m.group(1), row['inode_id']))
                
    
    event = LiveAttachements()
    event.periodic(dbh, dbh.case)
