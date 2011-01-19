import gtk
import gedit
import sys
import math

class struct:pass

def indent(s):
  x = 0
  for c in s:
    if c == ' ':
      x += 1
    else:
      break
  return x
  
def probj(ob):
  meths = dir(ob)
  meths.sort()
  for i, m in enumerate(meths):
    print '%-26s'%m,
    if i and i%3==0:
      print
  print ob

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
  try:
    return cr.text_extents(str)
  except MemoryError:
    pass
    
  x, y = cr.get_current_point()
  cr.move_to(0,-5)
  cr.show_text(str)
  nx,ny = cr.get_current_point()
  
  #print repr(str),x,nx,y,ny
  ascent, descent, height, max_x_advance, max_y_advance = cr.font_extents()
  cr.move_to(x,y)
  
  return 0, 0, nx, height, 0, 0
  
def fit_text(str, w, h, cr):
  moved_downP = False
  originalx,_ = cr.get_current_point()
  sofarH = 0
  while 1:
    for i in range(len(str)):
      _, _, tw, th, _, _ = text_extents(str[:i],cr)
      #_, _, tw, th, _, _ = cr.text_extents(str[:i])
      if tw > w:
        break
    disp = str[:i+1]
    str = str[i+1:]
    _, _, tw, th, _, _ = text_extents(disp,cr)
    #_, _, tw, th, _, _ = cr.text_extents(disp)
    sofarH += th
    if sofarH > h:
      return
    if not moved_downP:
      moved_downP = True
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
    
    cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
    cr.show_text(disp)
    cr.rel_move_to(0,th+3)
    x,y = cr.get_current_point()
    cr.move_to(originalx,y)
    if not str:
      break
      
def downsample_lines(lines, h):
  n = len(lines)
  
  # pick scale
  for scale in (3,2,1): 
    maxlines_ = h/(.85*scale)
    if n < 1.5*maxlines_:
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
      
def visible_lines_top_bottom(geditwindow):
  view = me.geditwindow.get_active_view()
  rect = view.get_visible_rect()
  topiter, _ = view.get_line_at_y(rect.y)
  botiter, _ = view.get_line_at_y(rect.y+rect.height)
  return topiter.get_line(), botiter.get_line()
      
def scrollbar(lines,topI,botI,w,h,cr,scrollbarW=4):
  "top and bot a passed as line indices"
  topY = None
  botY = None
  for line in lines:
    if not topY:
      if line.i >= topI:
        topY = line.y
    if not botY:
      if line.i >= botI:
        botY = line.y
        
  cr.set_source_rgb(.1,.1,.1)
  cr.rectangle(w-scrollbarW,0,scrollbarW,h)
  cr.fill()
  
  
class TextmapView(gtk.VBox):
  def __init__(me, geditwindow):
    gtk.VBox.__init__(me)
    
    me.geditwindow = geditwindow
    
    darea = gtk.DrawingArea()
    darea.connect("expose-event", me.expose)
    
    darea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
    darea.connect("button-press-event", me.button_press)
    
    me.pack_start(darea, True, True)
    
    me.darea = darea
    #probj(me.darea)
    me.show_all()
    
  def button_press(me, widget, event):
    print 'button_press',event.x, event.y
    for line in me.lines:
      if line.y > event.y:
        break
    #print line.i, repr(line.raw)
    view = me.geditwindow.get_active_view()
    doc = me.geditwindow.get_active_tab().get_document()
    doc.place_cursor(doc.get_iter_at_line_index(line.i,0))
    view.scroll_to_cursor()
    
  def expose(me, widget, event):
    #print 'expose',me.geditwindow.get_active_tab().get_document().get_uri(),[d.get_uri() for d in me.geditwindow.get_documents()]
    doc = me.geditwindow.get_active_tab().get_document()
    lines = document_lines(doc)
    try:
      win = widget.get_window()
    except AttributeError:
      win = widget.window
    w,h = map(float,win.get_size())
    cr = widget.window.cairo_create()
    
    #probj(cr)
       
    # bg
    if 1:
      cr.set_source_rgb(46/256.,52/256.,54/256.)
      cr.move_to(0,0)
      cr.rectangle(0,0,w,h)
      cr.fill()
      cr.move_to(0,0)
    
    if not lines:
      return
      
    lines, scale, downsampled = downsample_lines(lines, h)
    
    lines = lines_add_section_len(lines)
    
    n = len(lines)
    lineH = h/n
    
    #print 'doc',doc.get_uri(), lines[0].raw
    
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
          _,_,tw,th,_,_= text_extents(line.raw,cr)
          #_,_,tw,th,_,_= cr.text_extents(line.raw)
          #print th
          cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
          cr.show_text(line.raw)
          if downsampled:
            sofarH += lineH
          else:
            sofarH += th
        else:
          if downsampled:
            sofarH += lineH
          else:
            sofarH += scale-1
        
      if line.section:
        sections.append((line, lastH))
        
      cr.move_to(0, sofarH)
        
    for line, lastH in sections:
    
      cr.move_to(0, lastH)
    
      cr.set_line_width(1)
      cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
      #cr.move_to(0,rectH*i)
      cr.line_to(w,lastH)
      cr.stroke()
      
      cr.move_to(0,lastH)
      cr.set_font_size(12)
      cr.set_source_rgb(0xd3/256.,0xd7/256.,0xcf/256.)
      fit_text(line.section,4*w/5,line.section_len*rectH,cr)
      
    topL,botL = visible_lines_top_bottom(me.geditwindow)
    scrollbar(lines,topL,botL,w,h,cr)
      
    me.lines = lines
      
        
class ExamplePyWindowHelper:
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
    try:
      win = me.textmapview.darea.get_window()
    except AttributeError:
      win = me.textmapview.darea.window
    if win:
      w,h = win.get_size()
      me.textmapview.darea.queue_draw_area(0,0,w,h)
    
class ExamplePyPlugin(gedit.Plugin):
  def __init__(me):
    gedit.Plugin.__init__(me)
    me._instances = {}

  def activate(me, window):
    me._instances[window] = ExamplePyWindowHelper(me, window)

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
