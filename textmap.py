# Copyright 2011, Dan Gindikin <dgindikin@gmail.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

import gtk
import gedit
import sys
import math
import cairo
import re
import copy

version = "0.1 beta"

# ------------------------------------------------------------------------------
# These regular expressions are applied in sequence ot each line, to determine
# whether it is a section start or not

SectionREs = (
  re.compile('def\s*(\w+)\s*\('),                          # python method
  re.compile('class\s*(\w+)\s*[(:]'),                      # python class 
  re.compile('cdef\s*class\s*(\w+)\s*[(:]'),               # cython class
  re.compile('cdef\s*(?:[\w\.]*?\**\s*)?(\w+)\s*\('),      # cython method
)

SubsectionREs = (
  re.compile('\s+def\s*(\w+)\s*\('),                       # python class method
  re.compile('\s+cdef\s*(?:[\w\.]*?\**\s*)?(\w+)\s*\('),   # cython class method
)

# ------------------------------------------------------------------------------

class struct:pass

def indent(s):
  x = 0
  for c in s:
    if c == ' ':
      x += 1
    else:
      break
  return x
  
def probj(ob,*substrs):
  meths = dir(ob)
  meths.sort()
  print ob,type(ob)
  for m in meths:
    doprint=True
    if substrs:
      doprint=False
      for s in substrs:
        if s in m:
          doprint=True
          break
    if doprint:
      print '%40s'%m
      
def match_RE_list(str, REs):
  for r in REs:
    m = r.match(str)
    if m:
      return m.groups()[0]
  return None

def document_lines(document):
  if not document:
    return None
  #print 'document_lines',document
  STR = document.get_property('text')
  lines = STR.split('\n')
  ans = []
  for i,each in enumerate(lines):
    x = struct()
    x.i = i
    x.len = len(each)
    x.indent = indent(each)
    x.raw = each
    x.section = match_RE_list(x.raw,SectionREs)
    x.subsection = None
    if not x.section:
      x.subsection = match_RE_list(x.raw,SubsectionREs)
    ans.append(x)
  return ans
  
def lines_add_section_len(lines):
  line_prevsection = None
  counter = 0
  for i, line in enumerate(lines):
    if line.section:
      if line_prevsection:
        line_prevsection.section_len = counter
      line_prevsection = line
      counter = 0
    counter += 1
  if line_prevsection:
    line_prevsection.section_len = counter
  return lines
  
def text_extents(str,cr):
  "code around bug in older cairo"
  #try:
  #  return cr.text_extents(str)
  #except MemoryError:
  #  pass
    
  if str:
    x, y = cr.get_current_point()
    cr.move_to(0,-5)
    cr.show_text(str)
    nx,ny = cr.get_current_point()
    cr.move_to(x,y)
  else:
    nx = 0
    ny = 0
  
  #print repr(str),x,nx,y,ny
  ascent, descent, height, max_x_advance, max_y_advance = cr.font_extents()
  
  return nx, height
  
def fit_text(str, w, h, fg, bg, cr):
  moved_down = False
  originalx,_ = cr.get_current_point()
  sofarH = 0
  rn = []
  if dark(*bg):
    bg_rect_C = lighten(.1,*bg)
  else:
    bg_rect_C = darken(.1,*bg)
    
  while 1:
    # find the next chunk of the string that fits
    for i in range(len(str)):
      tw, th = text_extents(str[:i],cr)
      if tw > w:
        break
    disp = str[:i+1]
    str = str[i+1:]
    tw, th = text_extents(disp,cr)
    
    sofarH += th
    if sofarH > h:
      return rn
    if not moved_down:
      moved_down = True
      cr.rel_move_to(0, th)
      
    # bg rectangle
    x,y = cr.get_current_point()
    #cr.set_source_rgba(46/256.,52/256.,54/256.,.75)
    cr.set_source_rgba(bg_rect_C[0],bg_rect_C[1],bg_rect_C[2],.75)
    if str:
      cr.rectangle(x,y-th+2,tw,th+3)
    else: # last line does not need a very big rectangle
      cr.rectangle(x,y-th+2,tw,th)    
    cr.fill()
    cr.move_to(x,y)
    
    # actually display
    cr.set_source_rgb(*fg)
    cr.show_text(disp)
    
    # remember
    rec = struct()
    rec.x = x
    rec.y = y
    rec.th = th
    rec.tw = tw
    rn.append(rec)
    
    cr.rel_move_to(0,th+3)
    x,y = cr.get_current_point()
    cr.move_to(originalx,y)
    
    if not str:
      break
  return rn
      
def downsample_lines(lines, h, max_scale=3):
  n = len(lines)
  
  # pick scale
  for scale in range(max_scale,0,-1): 
    maxlines_ = h/(.85*scale)
    if n < 3*maxlines_:
      break
      
  if n <= maxlines_:
    downsampled = False
    return lines, scale, downsampled
    
  # need to downsample
  lines[0].score = sys.maxint # keep the first line
  for i in range(1, len(lines)):
    if lines[i].section:  # keep sections
      lines[i].score = sys.maxint
    elif lines[i].subsection:
      lines[i].score = sys.maxint/2
    elif lines[i].changed:
      lines[i].score = sys.maxint/2
    else:
      if 0: # get rid of lines that are very different
        lines[i].score = abs(lines[i].indent-lines[i-1].indent) \
                         + abs(len(lines[i].raw)-len(lines[i-1].raw))
      if 1: # get rid of lines randomly
        lines[i].score = hash(lines[i].raw)
        if lines[i].score > sys.maxint/2:
          lines[i].score -= sys.maxint/2
                     
  scoresorted = sorted(lines, lambda x,y: cmp(x.score,y.score))
  erasures_ = int(math.ceil(n - maxlines_))
  #print 'erasures_',erasures_
  scoresorted[0:erasures_]=[]
    
  downsampled = True
  
  return sorted(scoresorted, lambda x,y:cmp(x.i,y.i)), scale, downsampled
      
def visible_lines_top_bottom(geditwin):
  view = geditwin.get_active_view()
  rect = view.get_visible_rect()
  topiter = view.get_line_at_y(rect.y)[0]
  botiter = view.get_line_at_y(rect.y+rect.height)[0]
  return topiter.get_line(), botiter.get_line()
      
def dark(r,g,b):
  "return whether the color is light or dark"
  if r+g+b < 1.5:
    return True
  else:
    return False
    
def darken(fraction,r,g,b):
  return r-fraction*r,g-fraction*g,b-fraction*b
  
def lighten(fraction,r,g,b):
  return r+(1-r)*fraction,g+(1-g)*fraction,b+(1-b)*fraction
  
def scrollbar(lines,topI,botI,w,h,bg,cr,scrollbarW=10):
  "top and bot a passed as line indices"
  # figure out location
  topY = None
  botY = None
  for line in lines:
    if not topY:
      if line.i >= topI:
        topY = line.y
    if not botY:
      if line.i >= botI:
        botY = line.y
  
  if topY is None:
    topY = 0
  if botY is None:
    botY = lines[-1].y

  if 0: # bg rectangle     
    cr.set_source_rgba(.1,.1,.1,.35)
    cr.rectangle(w-scrollbarW,0,scrollbarW,topY)
    cr.fill()
    cr.rectangle(w-scrollbarW,botY,scrollbarW,h-botY)
    cr.fill()
    
  if 0: # scheme 1
    cr.set_line_width(1)
    #cr.set_source_rgb(0,0,0)
    #cr.set_source_rgb(1,1,1)
    cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
    if 0: # big down line
      cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
      cr.move_to(w-scrollbarW/2.,0)
      cr.line_to(w-scrollbarW/2.,topY)
      cr.stroke()
      cr.move_to(w-scrollbarW/2.,botY)
      cr.line_to(w-scrollbarW/2.,h)
      cr.stroke()
    if 0:
      cr.rectangle(w-scrollbarW,topY,scrollbarW-1,botY-topY)
      cr.stroke()
    if 1: # bottom lines
      #cr.set_line_width(2)
      #cr.move_to(w-scrollbarW,topY)
      cr.move_to(0,topY)
      cr.line_to(w,topY)
      cr.stroke()
      cr.move_to(0,botY)
      cr.line_to(w,botY)
      cr.stroke()
    if 0: # rect
      cr.set_source_rgba(.5,.5,.5,.1)
      #cr.set_source_rgba(.1,.1,.1,.35)
      #cr.rectangle(w-scrollbarW,topY,scrollbarW,botY-topY)
      cr.rectangle(0,topY,w,botY-topY)
      cr.fill()
      
  if 0: # scheme 2
    cr.set_line_width(3)
    cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
    if 1: # bottom lines
      cr.move_to(0,topY)
      cr.line_to(w,topY)
      cr.stroke()
      cr.move_to(0,botY)
      cr.line_to(w,botY)
      cr.stroke()
    if 1: # side lines
      cr.set_line_width(2)
      len = (botY-topY)/8
      margin = 1
      if 0: # left
        cr.move_to(margin,topY)
        cr.line_to(margin,topY+len)
        cr.stroke()
        cr.move_to(margin,botY-len)
        cr.line_to(margin,botY)
        cr.stroke()
      if 1: # right
        cr.move_to(w-margin,topY)
        cr.line_to(w-margin,topY+len)
        cr.stroke()
        cr.move_to(w-margin,botY-len)
        cr.line_to(w-margin,botY)
        cr.stroke()
    if 0: # center
      len = (botY-topY)/5
      cx = w/2
      cy = topY+(botY-topY)/2
      if 1: # vert
        for x in (cx,):#(cx-len/2,cx,cx+len/2):
          cr.move_to(x,cy-len/2)
          cr.line_to(x,cy+len/2)
          cr.stroke()
      if 0: # horiz
        cr.move_to(cx-len/2,cy)
        cr.line_to(cx+len/2,cy)
        cr.stroke()
    
  if 0: # view indicator  
    cr.set_source_rgba(.5,.5,.5,.5)
    #cr.set_source_rgba(.1,.1,.1,.35)
    cr.rectangle(w-scrollbarW,topY,scrollbarW,botY-topY)
    cr.fill()
    cr.rectangle(w-scrollbarW,topY,scrollbarW-1,botY-topY)
    cr.set_line_width(.5)
    cr.set_source_rgb(1,1,1)
    #cr.set_source_rgb(0,0,0)
    cr.stroke()
  
  if 0: # lines
    cr.set_source_rgb(1,1,1)
    cr.move_to(w,0)
    cr.line_to(w-scrollbarW,topY)
    cr.line_to(w-scrollbarW,botY)
    cr.line_to(w,h)
    cr.stroke()
    
  if 0: # scheme 3
  
    if 1: # black lines
      cr.set_line_width(2)
      cr.set_source_rgb(0,0,0)
      cr.move_to(0,topY)
      cr.line_to(w,topY)
      cr.stroke()
      cr.move_to(0,botY)
      cr.line_to(w,botY)
      cr.stroke() 
      
    if 1: # white lines
      cr.set_line_width(2)
      cr.set_dash([1,2])
      cr.set_source_rgb(1,1,1)
      cr.move_to(0,topY)
      cr.line_to(w,topY)
      cr.stroke()
      cr.move_to(0,botY)
      cr.line_to(w,botY)
      cr.stroke()   
  
  if 0: # scheme 4
    pat = cairo.LinearGradient(0,topY-10,0,topY)
    pat.add_color_stop_rgba(0, 1, 1, 1,1)
    pat.add_color_stop_rgba(1, .2,.2,.2,1)
    pat.add_color_stop_rgba(2, 0, 0, 0,1)
    cr.rectangle(0,topY-10,w,10)
    cr.set_source(pat)
    cr.fill()
    
  if 0: # triangle right
    # triangle
    size=12
    midY = topY+(botY-topY)/2
    cr.set_line_width(2)
    cr.set_source_rgb(1,1,1)
    cr.move_to(w-size-1,midY)
    cr.line_to(w-1,midY-size/2)
    #cr.stroke_preserve()
    cr.line_to(w-1,midY+size/2)
    #cr.stroke_preserve()
    cr.line_to(w-size-1,midY)
    cr.fill()
    # line
    cr.move_to(w-2,topY+2)
    cr.line_to(w-2,botY-2)
    cr.stroke()
    
  if dark(*bg):
    color = (1,1,1)
  else:
    color = (0,0,0)
    
  if 1: # triangle left
    # triangle
    size=12
    midY = topY+(botY-topY)/2
    cr.set_line_width(2)
    cr.set_source_rgb(*color)
    cr.move_to(size+1,midY)
    cr.line_to(1,midY-size/2)
    #cr.stroke_preserve()
    cr.line_to(1,midY+size/2)
    #cr.stroke_preserve()
    cr.line_to(size+1,midY)
    cr.fill()
    # line
    cr.move_to(2,topY+2)
    cr.line_to(2,botY-2)
    cr.stroke()
    
  if 1: # dashed lines
    cr.set_line_width(2)
    cr.set_source_rgb(*color)
    cr.set_dash([8,8])
    #cr.rectangle(2,topY,w-4,botY-topY)
    cr.move_to(4,topY); cr.line_to(w,topY)
    cr.stroke()
    cr.move_to(4,botY); cr.line_to(w,botY)
    cr.stroke()
        
def queue_refresh(textmapview):
  try:
    win = textmapview.darea.get_window()
  except AttributeError:
    win = textmapview.darea.window
  if win:
    w,h = win.get_size()
    textmapview.darea.queue_draw_area(0,0,w,h)
    
def str2rgb(s):
  assert s.startswith('#') and len(s)==7,('not a color string',s)
  r = int(s[1:3],16)/256.
  g = int(s[3:5],16)/256.
  b = int(s[5:7],16)/256.
  return r,g,b
  
def mark_changed_lines(original,current):
  
  # assume to start everything was changed, except for empties
  for line in current:
    if not line.raw.strip():
      line.changed = False
    else:
      line.changed = True
  
  # now go through and find original lines in current
  original_lines_found = []
  
  consumed_=0
  for oline in original:
    if not oline.raw.strip():
      continue # skip empties, they are too confusing
    for c in range(consumed_,len(current)):
      if oline.raw == current[c].raw: # Found it!
        original_lines_found.append(c)
        consumed_ = c + 1   # only search through current line from this point forward
        break
      

  # mark all the unchanged lines we found
  for c in original_lines_found:
    current[c].changed = False
    
  #print original_lines_found,len(original),len(current)

  return current
      
class TextmapView(gtk.VBox):
  def __init__(me, geditwin):
    gtk.VBox.__init__(me)
    
    me.geditwin = geditwin
    
    darea = gtk.DrawingArea()
    darea.connect("expose-event", me.expose)
    
    darea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
    darea.connect("button-press-event", me.button_press)
    darea.connect("scroll-event", me.on_darea_scroll_event)
    
    me.pack_start(darea, True, True)
    
    me.darea = darea
    #probj(me.darea)

    me.connected = {}
    me.draw_scrollbar_only = False
    me.topL = None
    me.surface_textmap = None
    
    me.line_count = 0
    
    me.doc_attached_data = {}
    
    me.show_all()
    
  def on_darea_scroll_event(me, widget, event):
    #print 'XXX on_darea_scroll_event'
    # somehow pass this on, scroll the document/view
    pass
    
  def on_doc_cursor_moved(me, doc):
    #new_line_count = doc.get_line_count()
    #print 'new_line_count',new_line_count
    topL = visible_lines_top_bottom(me.geditwin)[0]
    if topL <> me.topL:
      queue_refresh(me)
      me.draw_scrollbar_only = True
    
  def on_insert_text(me, doc, piter, text, len):
    pass
    #if len < 20 and '\n' in text:
    #  print 'piter',piter,'text',repr(text),'len',len
    
  def button_press(me, widget, event):
    #print 'on_button_press...'
    #print 'button_press',event.x, event.y
    for line in me.lines:
      if line.y > event.y:
        break
    #print line.i, repr(line.raw)
    view = me.geditwin.get_active_view()
    doc = me.geditwin.get_active_tab().get_document()
    doc.place_cursor(doc.get_iter_at_line_index(line.i,0))
    
    view.scroll_to_cursor()
    #print view
    
    queue_refresh(me)
    
  def on_scroll_event(me,view,event):
    #print 'on_scroll_event...'
    me.draw_scrollbar_only = True
    queue_refresh(me)
    
  def on_search_highlight_updated(me,doc,t,u):
    #print 'on_search_highlight_updated:'
    #print t.get_line(),u.get_line()
    pass
    
  def expose(me, widget, event):
    doc = me.geditwin.get_active_tab().get_document()
    if not doc:   # nothing open yet
      return
    
    if id(doc) not in me.connected:
      me.connected[id(doc)] = True
      doc.connect("cursor-moved", me.on_doc_cursor_moved)
      doc.connect("insert-text", me.on_insert_text)
      doc.connect("search-highlight-updated", me.on_search_highlight_updated)
      
    view = me.geditwin.get_active_view()
    if not view:
      return
    
    if id(view) not in me.connected:
      me.connected[id(view)] = True
      view.connect("scroll-event", me.on_scroll_event)
      
    style = None
    try:
      style = doc.get_style_scheme().get_style('text')
    except:
      pass  # probably an older version of gedit, not style schemes yet
      
    if style is None:
      bg = (0,0,0)
      fg = (1,1,1)
    else:
      fg,bg = map(str2rgb, style.get_properties('foreground','background'))
    changeCLR = (1,0,1)
      
    #print doc
       
    try:
      win = widget.get_window()
    except AttributeError:
      win = widget.window
    w,h = map(float,win.get_size())
    cr = widget.window.cairo_create()
    
    #probj(cr,'rgb')
    
    # Are we drawing everything, or just the scrollbar?
            
    if me.surface_textmap is None or not me.draw_scrollbar_only:
    
      lines = document_lines(doc)
      
      if id(doc) not in me.doc_attached_data:
        docrec = struct()
        me.doc_attached_data[id(doc)] = docrec
        docrec.original_lines = None # we skip the first one, its empty
        for l in lines:
          l.changed = False
      else:
        docrec = me.doc_attached_data[id(doc)]
        if docrec.original_lines == None:
          docrec.original_lines = copy.deepcopy(lines)
        lines = mark_changed_lines(docrec.original_lines, lines)
     
      cr.push_group()
      
      # bg
      if 1:
        #cr.set_source_rgb(46/256.,52/256.,54/256.)
        cr.set_source_rgb(*bg)
        cr.move_to(0,0)
        cr.rectangle(0,0,w,h)
        cr.fill()
        cr.move_to(0,0)
      
      if not lines:
        return
        
      # translate everthing in
      margin = 3
      cr.translate(margin,0)
      w -= margin # an d here
            
      max_scale = 3
      lines, scale, downsampled = downsample_lines(lines, h, max_scale=max_scale)
      
      stretch = False
      if downsampled or scale < max_scale:
        stretch = True
      
      lines = lines_add_section_len(lines)

      n = len(lines)
      lineH = h/n
      
      #print 'doc',doc.get_uri(), lines[0].raw
      
      # ------------------------ display text silhouette ------------------------
      
      rectH = h/float(len(lines))
      sofarH= 0
      sections = []
      for i, line in enumerate(lines):
      
        line.y = sofarH
        # text
        if 1:
          lastH = sofarH
          cr.set_font_size(scale)
          if line.raw.strip():
            tw,th = text_extents(line.raw,cr)
            if line.changed:
              cr.set_source_rgb(*changeCLR)
            else:
              cr.set_source_rgb(*fg)
            cr.show_text(line.raw)
            if stretch:
              sofarH += lineH
            else:
              sofarH += th
          else:
            if stretch:
              sofarH += lineH
            else:
              sofarH += scale-1
          
        if line.section:
          sections.append((line, lastH))
          
        cr.move_to(0, sofarH)
          
      # ------------------- display sections and subsections  ------------------

      # Subsections
      
      cr.new_path()
      cr.set_line_width(1.5)
      cr.set_source_rgb(*fg)
      subsW = 10
      subsmargin = 10
      for line in lines:
        if line.subsection:
          if 0:
            cr.move_to(subsmargin,line.y)
            cr.line_to(subsmargin+subsW,line.y)
          cr.arc(subsmargin,line.y+3,2,0,6.28)
          cr.stroke()
          
      # Sections
      for line, lastH in sections:
      
        if 0: # section lines
          cr.move_to(0, lastH)
          cr.set_line_width(1)
          #cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
          cr.set_source_rgb(*fg)
          cr.line_to(w,lastH)
          cr.stroke()
        
        if 1: # section heading
          cr.move_to(0,lastH)
          cr.set_font_size(12)
          #cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
          cr.set_source_rgb(*fg)
          dispnfo = fit_text(line.section,4*w/5,line.section_len*rectH,fg,bg,cr)
          
        if 0 and dispnfo: # section hatches
          cr.set_line_width(1)
          r=dispnfo[0] # first line
          cr.move_to(r.x+r.tw+2,r.y-r.th/2+2)
          cr.line_to(w,r.y-r.th/2+2)
          cr.stroke()
          
      # ------------------ translate back for the scroll bar -------------------
      
      cr.translate(-margin,0)
      w += margin

      # -------------------------- mark changed lines --------------------------
            
      cr.set_source_rgb(*changeCLR)
      for line in lines:
        if not line.changed:
          continue
        cr.rectangle(w-3,line.y-2,2,5) # dan was here
        cr.fill()
      
      # save
      me.surface_textmap = cr.pop_group() # everything but the scrollbar
      me.lines = lines

    cr.set_source(me.surface_textmap)
    cr.rectangle(0,0,w,h)
    cr.fill()
        
    # ------------------------------- scrollbar -------------------------------

    topL,botL = visible_lines_top_bottom(me.geditwin)
    
    scrollbar(me.lines,topL,botL,w,h,bg,cr)
    
    me.topL = topL
    me.draw_scrollbar_only = False
      
        
class TextmapWindowHelper:
  def __init__(me, plugin, window):
    me.window = window
    me.plugin = plugin

    panel = me.window.get_side_panel()
    image = gtk.Image()
    image.set_from_stock(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_BUTTON)
    me.textmapview = TextmapView(me.window)
    me.ui_id = panel.add_item(me.textmapview, "TextMap", image)
    
    me.panel = panel

  def deactivate(me):
    me.window = None
    me.plugin = None
    me.textmapview = None

  def update_ui(me):
    queue_refresh(me.textmapview)
    
class TextmapPlugin(gedit.Plugin):
  def __init__(me):
    gedit.Plugin.__init__(me)
    me._instances = {}

  def activate(me, window):
    me._instances[window] = TextmapWindowHelper(me, window)

  def deactivate(me, window):
    if window in me._instances:
      me._instances[window].deactivate()

  def update_ui(me, window):
    # Called whenever the window has been updated (active tab
    # changed, etc.)
    #print 'plugin.update_ui'
    if window in me._instances:
      me._instances[window].update_ui()
      #window.do_expose_event()
