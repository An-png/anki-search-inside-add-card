# anki-search-inside-add-card
# Copyright (C) 2019 - 2020 Tom Z.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import utility.text
import html
import typing
from typing import Tuple, List, Any, Optional

from datetime import datetime, timedelta
from .web_import import import_webpage
from .config import get_config_value_or_default


class Printable():
    
    def get_content(self) -> str:
        """
        Should return the "body" of the note, e.g. the 'source' field in case of index notes and the 
        'text' field in case of SiacNote.
        """
        raise NotImplementedError()

class SiacNote(Printable):

    note_type       = "user"
    MISSED_NOTES    = get_config_value_or_default("notes.queue.missedNotesHandling", "remove-schedule")

    def __init__(self, props: Tuple[Any, ...]):
        self.id             : int           = props[0]
        self.title          : str           = props[1]
        self.text           : str           = props[2]
        self.source         : str           = props[3]
        self.tags           : str           = props[4]
        self.nid            : int           = props[5]
        self.created        : str           = props[6]
        self.modified       : str           = props[7]
        self.reminder       : str           = props[8]
        self.lastscheduled  : str           = props[9]
        self.position       : int           = props[10]
        self.extract_start  : Optional[int] = props[11]
        self.extract_end    : Optional[int] = props[12]
        self.delay          : Optional[str] = props[13]

        self.mid            : int = -1
    
    @staticmethod
    def from_index(index_props: Tuple[Any, ...]) -> 'SiacNote':

        id      = index_props[0]
        # if the note was stored in the index, its title, text, and source fields are collapsed into a single field, separated by \u001f
        text    = index_props[4]
        title   = text.split("\u001f")[0]
        body    = text.split("\u001f")[1]
        src     = text.split("\u001f")[2]

        return SiacNote((id, title, body, src, index_props[2], -1, "", "", "", "", -1, None, None, None))

    def get_content(self) -> str:
        return self._build_non_anki_note_html()

    def is_pdf(self) -> bool:
        return self.source is not None and self.source.strip().lower().endswith(".pdf")
    
    def is_feed(self) -> bool:
        return self.source is not None and self.source.strip().lower().startswith("feed:")
    
    def is_in_queue(self) -> bool:
        return self.position is not None and self.position >= 0

    def get_title(self) -> str:
        if self.title is None or len(self.title.strip()) == 0:
            return "Untitled"
        return self.title
    
    def get_containing_folder(self) -> Optional[str]:
        if not self.is_pdf():
            return None
        source = self.source[:self.source.rindex("/")]
        return source

    def is_due_today(self) -> bool:
        if self.reminder is None or len(self.reminder.strip()) == 0 or not "|" in self.reminder:
            return False
        dt = datetime.strptime(self.reminder.split("|")[1], '%Y-%m-%d-%H-%M-%S')
        return dt.date() == datetime.today().date()
    
    def is_scheduled(self) -> bool:
        if self.reminder is None or len(self.reminder.strip()) == 0 or not "|" in self.reminder:
            return False
        if SiacNote.MISSED_NOTES != "place-front":
            return self.is_due_today()
        return self.is_or_was_due()

    def is_or_was_due(self) -> bool:
        if self.reminder is None or len(self.reminder.strip()) == 0 or not "|" in self.reminder:
            return False
        dt = datetime.strptime(self.reminder.split("|")[1], '%Y-%m-%d-%H-%M-%S')
        return dt.date() <= datetime.today().date()
    
    def is_due_sometime(self) -> bool:
        if self.reminder is None or len(self.reminder.strip()) == 0 or not "|" in self.reminder:
            return False
        return True
    
    def current_due_date(self) -> Optional[datetime]:
        if not self.is_due_sometime():
            return None
        return datetime.strptime(self.reminder.split("|")[1], '%Y-%m-%d-%H-%M-%S')

    def due_days_delta(self) -> int:
        return (datetime.now().date() - self.current_due_date().date()).days
        
    def schedule_type(self) -> str:
        return self.reminder.split("|")[2][:2]
    
    def schedule_value(self) -> str:
        return self.reminder.split("|")[2][3:]

    def _build_non_anki_note_html(self) -> str:
        """
        User's notes should be displayed in a way to visually distinguish between title, text and source.
        Also, text might need to be cut if is too long to reduce time needed for highlighting, extracting keywords, and rendering.
        """
        src     = self.source
        title   = html.escape(self.title)
        body    = self.text
        #trim very long texts:
        if len(body) > 3000:
            #there might be unclosed tags now, but parsing would be too much overhead, so simply remove div, a and span tags
            #there might be still problems with <p style='...'>
            body                = body[:3000]
            body                = utility.text.remove_tags(body, ["div", "span", "a"])
            last_open_bracket   = body.rfind("<")

            if last_open_bracket >= len(body) - 500 or body.rfind(" ") < len(body) - 500:
                last_close_bracket = body.rfind(">")
                if last_close_bracket < last_open_bracket:
                    body = body[:last_open_bracket]

            body += "<br></ul></b></i></em></span></p></a></p><p style='text-align: center; user-select: none;'><b>(Text was cut - too long to display)</b></p>"
        
        title   = "%s<b>%s</b>%s" % ("<span class='siac-pdf-icon'></span>" if self.is_pdf() else "", title if len(title) > 0 else "Unnamed Note", "<hr style='margin-bottom: 5px; border-top: dotted 2px;'>" if len(body.strip()) > 0 else "")

        # add the source, separated by a line
        if src is not None and len(src) > 0 and get_config_value_or_default("notes.showSource", True):
            if "/" in src and src.endswith(".pdf"):
                src = src[src.rindex("/") +1:]
            src = "<br/><hr style='border-top: dotted 2px;'><i>Source: %s</i>" % (src)
        else:
            src = ""
      
        return title + body + src

class IndexNote(Printable):

    note_type: str = "index"

    def __init__(self, props: Tuple[Any, ...]):
        self.id     = props[0]
        self.text   = props[1]
        self.tags   = props[2]
        self.did    = props[3]
        self.source = props[4]
        self.rank   = props[5]
        self.mid    = props[6]
        self.refs   = props[7]


    def get_content(self) -> str:
        return self.source

class NoteRelations():
    def __init__(self, related_by_title: List[SiacNote], related_by_tags: List[SiacNote], related_by_folder: List[SiacNote]):
        self.related_by_title   = related_by_title
        self.related_by_tags    = related_by_tags
        self.related_by_folder  = related_by_folder