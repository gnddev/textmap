import gtk
import gedit
import sys
import math
import cairo

class struct:pass

def indent(s):
  x = 0
  for c in s:
    if c == ' ':
      x += 1
    else:
      break
  return x
  
def probj(ob,substr=None):
  meths = dir(ob)
  meths.sort()
  if substr:
    meths = [s for s in meths if substr in s]
  for i, m in enumerate(meths):
    if i%2==0:
      print
    print '%-40s'%m,
  print

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
    if x.indent == 0 and x.raw.startswith('def') or x.raw.startswith('class'):
      x.section = x.raw.split(' ',1)[1].split('(')[0]
    else:
      x.section = None
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
  
def fit_text(str, w, h, cr):
  moved_down = False
  originalx,_ = cr.get_current_point()
  sofarH = 0
  rn = []
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
    cr.set_source_rgba(46/256.,52/256.,54/256.,.75)
    if str:
      cr.rectangle(x,y-th+2,tw,th+6)
    else: # last line does not need a very big rectangle
      cr.rectangle(x,y-th+2,tw,th)    
    cr.fill()
    cr.move_to(x,y)
    
    # actually display
    cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
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
    if n < 1.8*maxlines_:
      break
      
  if n <= maxlines_:
    downsampled = False
    return lines, scale, downsampled
    
  # need to downsample
  lines[0].score = sys.maxint # keep the first line
  for i in range(1, len(lines)):
    if lines[i].section:  # keep sections
      lines[i].score = sys.maxint
      continue
    lines[i].score = abs(lines[i].indent-lines[i-1].indent) \
                     + abs(len(lines[i].raw)-len(lines[i-1].raw))
                     
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
      
def scrollbar(lines,topI,botI,w,h,cr,scrollbarW=10):
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
    
  if 1: # triangle left
    # triangle
    size=12
    midY = topY+(botY-topY)/2
    cr.set_line_width(2)
    cr.set_source_rgb(1,1,1)
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
    cr.set_source_rgb(1,1,1)
    cr.set_dash([8,8])
    #cr.rectangle(2,topY,w-4,botY-topY)
    cr.move_to(4,topY); cr.line_to(w,topY)
    cr.stroke()
    cr.move_to(4,botY); cr.line_to(w,botY)
    cr.stroke()
        
def refresh(textmapview):
  try:
    win = textmapview.darea.get_window()
  except AttributeError:
    win = textmapview.darea.window
  if win:
    w,h = win.get_size()
    textmapview.darea.queue_draw_area(0,0,w,h)
      
class TextmapView(gtk.VBox):
  def __init__(me, geditwin):
    gtk.VBox.__init__(me)
    
    me.geditwin = geditwin
    
    darea = gtk.DrawingArea()
    darea.connect("expose-event", me.expose)
    
    darea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
    darea.connect("button-press-event", me.button_press)
    
    me.pack_start(darea, True, True)
    
    me.darea = darea
    #probj(me.darea)

    me.connected = False
    me.draw_scrollbar_only = False
    me.topL = None
    me.surface_textmap = None
    
    me.line_count = 0
    
    me.show_all()
    
  def on_doc_cursor_moved(me, doc):
    #new_line_count = doc.get_line_count()
    #print 'new_line_count',new_line_count
    topL = visible_lines_top_bottom(me.geditwin)[0]
    if topL <> me.topL:
      refresh(me)
      me.draw_scrollbar_only = True
    
  def on_insert_text(me, doc, piter, text, len):
    if len < 20 and '\n' in text:
      print 'piter',piter,'text',repr(text),'len',len
    
  def button_press(me, widget, event):
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
    
    refresh(me)
    
  def on_scroll_event(me,view,event):
    #print 'scroll',view,event
    me.draw_scrollbar_only = True
    refresh(me)
    
  def expose(me, widget, event):
    #print 'expose',me.geditwin.get_active_tab().get_document().get_uri(),[d.get_uri() for d in me.geditwin.get_documents()]
    doc = me.geditwin.get_active_tab().get_document()
    
    if not me.connected:
      me.connected = True
      doc.connect("cursor-moved", me.on_doc_cursor_moved)
      doc.connect("insert-text", me.on_insert_text)
      view = me.geditwin.get_active_view()
      #probj(view,'get')
      view.connect("scroll-event", me.on_scroll_event)
      
    #print doc
    
    lines = document_lines(doc)
    try:
      win = widget.get_window()
    except AttributeError:
      win = widget.window
    w,h = map(float,win.get_size())
    cr = widget.window.cairo_create()
    
    #probj(cr)
    
    if me.surface_textmap is None or not me.draw_scrollbar_only:
     
      cr.push_group()
        
      # bg
      if 1:
        cr.set_source_rgb(46/256.,52/256.,54/256.)
        cr.move_to(0,0)
        cr.rectangle(0,0,w,h)
        cr.fill()
        cr.move_to(0,0)
      
      if not lines:
        return
        
      # translate everthing in
      margin = 3
      cr.translate(margin,0)
      w -= margin
            
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
            cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.) # fg
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
          
      # ---------------------------- display sections ---------------------------
      
      for line, lastH in sections:
      
        if 0: # section lines
          cr.move_to(0, lastH)
          cr.set_line_width(1)
          cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
          cr.line_to(w,lastH)
          cr.stroke()
        
        if 1: # section heading
          cr.move_to(0,lastH)
          cr.set_font_size(12)
          cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
          dispnfo = fit_text(line.section,4*w/5,line.section_len*rectH,cr)
          
        if 0 and dispnfo: # section hatches
          cr.set_line_width(1)
          r=dispnfo[0] # first line
          cr.move_to(r.x+r.tw+2,r.y-r.th/2+2)
          cr.line_to(w,r.y-r.th/2+2)
          cr.stroke()
        
      # translate back for the scroll bar
      cr.translate(-margin,0)
      w += margin
      me.surface_textmap = cr.pop_group() # everything but the scrollbar
      me.lines = lines

    cr.set_source(me.surface_textmap)
    cr.rectangle(0,0,w,h)
    cr.fill()
          
    # ------------------------------- scrollbar -------------------------------
    
    topL,botL = visible_lines_top_bottom(me.geditwin)
    
    scrollbar(me.lines,topL,botL,w,h,cr)
    
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
    #probj(me.panel)

  def deactivate(me):
    me.window = None
    me.plugin = None
    me.textmapview = None

  def update_ui(me):
    refresh(me.textmapview)
    
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
