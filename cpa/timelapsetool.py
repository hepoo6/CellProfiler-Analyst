'''
Dependencies:
NetworkX: http://www.lfd.uci.edu/~gohlke/pythonlibs/#networkx
PyGraphviz: http://www.lfd.uci.edu/~gohlke/pythonlibs/#pygraphviz
Graphviz 2.28, from here: http://www.graphviz.org/pub/graphviz/stable/windows/
configobj: https://pypi.python.org/pypi/configobj

To get PyGraphViz working with PyGraphviz, needed to do the following:
* Use DOS-paths in Graphviz installation, i.e., C:\Progra~2\ instead of C:\Program Files (x86)\
* No spaces in Graphviz folder, i.e, .\Graphviz\ instead of .\Graphviz 2.28\
* Add Graphviz bin folder to Windows path
otherwise will get error msg "Program dot not found in path."
'''
import wx
from wx.combo import OwnerDrawnComboBox as ComboBox
import networkx as nx
import numpy as np
from operator import itemgetter
#import matplotlib
#matplotlib.use('WXAgg')

#from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
#from matplotlib.backends.backend_wx import NavigationToolbar2Wx
#from matplotlib import pyplot, rcParams
#rcParams['font.size'] = 10

import logging
import time
import sortbin
from guiutils import get_main_frame_or_none
from dbconnect import DBConnect, image_key_columns, object_key_columns
from properties import Properties
from cpatool import CPATool
import tableviewer

# traits imports
from traits.api import HasTraits, Instance
from traitsui.api import View, Item, HSplit, Group

# mayavi imports
from mayavi import mlab
from mayavi.core.ui.api import MlabSceneModel, SceneEditor
from mayavi.core.ui.mayavi_scene import MayaviScene
from tvtk.pyface.scene import Scene
from tvtk.api import tvtk

# Modiying sys.path doesn't seem to work for some reason; b/c it's the search path for *modules*?
#import sys
#sys.path.append("C:\\Progra~2\\Graphviz\\bin") 
import os
os.environ["PATH"] = os.environ["PATH"] + ";C:\\Progra~2\\Graphviz\\bin" 

# Colormap names from an error msg (http://www.mail-archive.com/mayavi-users@lists.sourceforge.net/msg00615.html)
# TODO(?): Find a better way to captures these names
all_colormaps = ['Accent', 'Blues', 'BrBG', 'BuGn', 'BuPu', 'Dark2', 
                 'GnBu', 'Greens', 'Greys', 'OrRd', 'Oranges', 'PRGn', 
                 'Paired', 'Pastel1', 'Pastel2', 'PiYG', 'PuBu', 
                 'PuBuGn', 'PuOr', 'PuRd', 'Purples', 'RdBu', 'RdGy', 
                 'RdPu', 'RdYlBu', 'RdYlGn', 'Reds', 'Set1', 'Set2', 
                 'Set3', 'Spectral', 'YlGn', 'YlGnBu', 'YlOrBr', 
                 'YlOrRd', 'autumn', 'binary', 'black-white', 'blue-red', 
                 'bone', 'cool', 'copper', 'file', 'flag', 'gist_earth', 
                 'gist_gray', 'gist_heat', 'gist_ncar', 'gist_rainbow', 
                 'gist_stern', 'gist_yarg', 'gray', 'hot', 'hsv', 'jet', 
                 'pink', 'prism', 'spectral', 'spring', 'summer','winter']
all_colormaps.sort()

props = Properties.getInstance()

required_fields = ['series_id', 'group_id', 'timepoint_id','object_tracking_label']

db = DBConnect.getInstance()

def add_props_field(props):
    # Temp declarations; these will be retrieved from the properties file directly
    props.series_id = ["Image_Group_Number"]
    #props.series_id = ["Image_Metadata_Plate"]
    props.group_id = "Image_Group_Number"
    props.timepoint_id = "Image_Group_Index"
    obj = props.cell_x_loc.split('_')[0]
    props.object_tracking_label = obj + "_TrackObjects_Label"
    props.parent_fields = ["%s_%s"%(obj,item) for item in ["TrackObjects_ParentImageNumber","TrackObjects_ParentObjectNumber"]]
    return props

def retrieve_datasets():
    series_list = ",".join(props.series_id)
    all_datasets = [x[0] for x in db.execute("SELECT %s FROM %s GROUP BY %s"%(series_list,props.image_table,series_list))]
    return all_datasets

def retrieve_trajectories(selected_dataset, selected_measurement):
    def parse_dataset_selection(s):
        return [x.strip() for x in s.split(',') if x.strip() is not '']
    
    selection_list = parse_dataset_selection(selected_dataset)
    dataset_clause = " AND ".join(["I.%s = '%s'"%(x[0], x[1]) for x in zip(props.series_id, selection_list)])
    query = ["SELECT O.%s, O.%s, O.%s, O.%s, O.%s, I.%s, O.%s, %s"%(
        props.object_tracking_label, props.image_id, props.object_id, props.cell_x_loc, props.cell_y_loc, props.timepoint_id, selected_measurement, ",".join(["O.%s"%item for item in props.parent_fields]) )]
    query.append("FROM %s AS I, %s AS O"%(props.image_table, props.object_table))
    query.append("WHERE I.%s = O.%s AND %s"%(props.image_id, props.image_id, dataset_clause))
    #query.append("AND I.%s <= 5 "%props.timepoint_id)
    #query.append("GROUP BY I.%s, O.%s "%(props.timepoint_id,props.object_tracking_label)) # The Brugge data has the same label in multiple locations in the same image (?!) This line filters them out.
    query.append("ORDER BY O.%s, I.%s"%(props.object_tracking_label, props.timepoint_id))
    data = db.execute(" ".join(query))
    columns = [props.object_tracking_label, props.image_id, props.object_id, props.cell_x_loc, props.cell_y_loc, props.timepoint_id, selected_measurement, props.parent_fields]
    #all_labels = np.unique([item[0] for item in locations])
    #trajectory_info = dict( (x,{"label":[],"db_key":[],"x":[],"y":[],"t":[],"s":[],"parent":[]}) for x in all_labels ) # Wanted to use fromkeys, but it leads to incorrect behavior since it passes by reference not by value
    #for d in data:
        #trajectory_info[d[0]]["label"].append(d[0])
        #trajectory_info[d[0]]["db_key"].append((d[1],d[2]))
        #trajectory_info[d[0]]["x"].append(d[3])
        #trajectory_info[d[0]]["y"].append(d[4])
        #trajectory_info[d[0]]["t"].append(d[5])
        #trajectory_info[d[0]]["s"].append(d[6])
        #trajectory_info[d[0]]["parent"].append((d[7],d[8]))
    #return trajectory_info
    return columns,data

################################################################################
class TimeLapseControlPanel(wx.Panel):
    '''
    A panel with controls for selecting the data for a visual
    '''

    def __init__(self, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)

        # Get names of data sets
        all_datasets = retrieve_datasets()

        # Get names of fields
        measurements = db.GetColumnNames(props.object_table)
        coltypes = db.GetColumnTypes(props.object_table)
        fields = [m for m,t in zip(measurements, coltypes) if t in [float, int, long]]

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Define widgets
        self.dataset_choice = ComboBox(self, -1, choices=[str(item) for item in all_datasets], size=(200,-1), style=wx.CB_READONLY)
        self.dataset_choice.Select(0)
        self.dataset_choice.SetHelpText("Select the time-lapse data set to visualize.")
        self.measurement_choice = ComboBox(self, -1, choices=fields, style=wx.CB_READONLY)
        self.measurement_choice.Select(0)
        self.measurement_choice.SetHelpText("Select the per-%s measurement to visualize the data with. The lineages and (xyt) trajectories will be color-coded by this measurement."%props.object_name[0])
        self.colormap_choice = ComboBox(self, -1, choices=all_colormaps, style=wx.CB_READONLY)
        self.colormap_choice.SetStringSelection("jet") 
        self.colormap_choice.SetHelpText("Select the colormap to use for color-coding the data.")
        self.trajectory_selection_button = wx.Button(self, -1, "Select Tracks to Visualize...")
        self.trajectory_selection_button.SetHelpText("Select the trajectories to show or hide in both panels.")
        self.update_plot_button = wx.Button(self, -1, "Update")
        self.update_plot_button.SetHelpText("Press this button after making selections to update the panels.")
        self.help_button = wx.ContextHelpButton(self)

        # Arrange widgets
        # Row #1: Dataset drop-down + track selection button
        sz = wx.BoxSizer(wx.HORIZONTAL)
        sz.Add(wx.StaticText(self, -1, "Data source:"), 0, wx.TOP, 4)
        sz.AddSpacer((4,-1))
        sz.Add(self.dataset_choice, 1, wx.EXPAND)
        sz.AddSpacer((4,-1))
        sz.Add(self.trajectory_selection_button)
        sizer.Add(sz, 1, wx.EXPAND)
        sizer.AddSpacer((-1,2))

        # Row #2: Measurement selection, colormap, update button
        sz = wx.BoxSizer(wx.HORIZONTAL)
        sz.Add(wx.StaticText(self, -1, "Measurement:"), 0, wx.TOP, 4)
        sz.AddSpacer((4,-1))
        sz.Add(self.measurement_choice, 1, wx.EXPAND)
        sz.AddSpacer((4,-1))
        sz.Add(wx.StaticText(self, -1, "Colormap:"), 0, wx.TOP, 4)
        sz.AddSpacer((4,-1))
        sz.Add(self.colormap_choice, 1, wx.EXPAND)
        sz.AddSpacer((4,-1))
        sz.Add(self.update_plot_button)
        sz.AddSpacer((4,-1))
        sz.Add(self.help_button)
        sizer.Add(sz, 1, wx.EXPAND)
        sizer.AddSpacer((-1,2))

        self.SetSizer(sizer)
        self.Show(True)
        
################################################################################
class MayaviView(HasTraits):
    """ Create a mayavi scene"""
    lineage_scene = Instance(MlabSceneModel, ())
    trajectory_scene = Instance(MlabSceneModel, ())
    
    # The layout of the dialog created
    view = View(HSplit(Group(Item('trajectory_scene',
                                  editor = SceneEditor(scene_class = Scene),
                                  #editor = SceneEditor(scene_class=MayaviScene),
                                  resizable=True, show_label=False)),
                       Group(Item('lineage_scene',
                                  editor = SceneEditor(scene_class = Scene),
                                  #editor = SceneEditor(scene_class=MayaviScene),
                                  resizable=True, show_label=False))),
                resizable=True)
    
    def __init__(self):
        HasTraits.__init__(self)

################################################################################
class TimeLapseTool(wx.Frame, CPATool):
    '''
    A time-lapse visual plot with its controls.
    '''
    def __init__(self, parent, size=(1000,600), **kwargs):
        wx.Frame.__init__(self, parent, -1, size=size, title='Time-Lapse Tool', **kwargs)
        CPATool.__init__(self)
        wx.HelpProvider_Set(wx.SimpleHelpProvider())
        self.SetName(self.tool_name)
        
        # Check for required properties fields.
        #fail = False
        #missing_fields = [field for field in required_fields if not props.field_defined(field)]
        #if missing_fields:
            #fail = True
            #message = 'The following missing fields are required for LineageTool: %s.'%(",".join(missing_fields))
            #wx.MessageBox(message,'Required field(s) missing')
            #logging.error(message)
        #if fail:    
            #self.Destroy()
            #return        

        self.control_panel = TimeLapseControlPanel(self)
        self.selected_dataset = self.control_panel.dataset_choice.GetStringSelection()
        self.selected_measurement = self.control_panel.measurement_choice.GetStringSelection()
        self.selected_colormap  = self.control_panel.colormap_choice.GetStringSelection()
        self.plot_updated = False
        self.trajectory_selected = False
        self.selected_node = None
        self.axes_opacity = 0.25
        self.do_plots_need_updating = {"dataset":True,"colormap":True,"measurement":True, "trajectories":True}
        
        self.mayavi_view = MayaviView()
        self.figure_panel = self.mayavi_view.edit_traits(
                                            parent=self,
                                            kind='subpanel').control
        navigation_help_text = ("Tips on navigating the plots:\n"
                                "Rotating the 3-D visualization: Place the mouse pointer over the visualization"
                                "window. Then left-click and drag the mouse pointer in the direction you want to rotate"
                                "the scene, much like rotating an actual object.\n\n"
                                "Zooming in and out: Place the mouse pointer over the visualization"
                                "window. To zoom into the scene, keep the right mouse button pressed and"
                                "drags the mouse upwards. To zoom out of the scene,  keep the right mouse button pressed"
                                "and drags the mouse downwards.\n\n"
                                "Panning: This can be done in one in two ways:\n"
                                "1. Keep the left mouse button pressed and simultaneously holding down the Shift key"
                                "and dragging the mouse in the appropriate direction.\n"
                                "2. Keep the middle mouse button pressed and dragging the mouse in the appropriate"
                                "direction\n\n"
                                "Please note that while the lineage panel can be rotated, zoomed and panned, it is a 2-D"
                                "plot so the top-down view is fixed.")
        self.figure_panel.SetHelpText(navigation_help_text)
        
        self.update_plot() 
        #self.obtain_tracking_data()
        #self.generate_graph()
        #self.draw_lineage()
        #self.draw_trajectories()
            
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.figure_panel, 1, wx.EXPAND)
        sizer.Add(self.control_panel, 0, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(sizer)
        
        self.figure_panel.Bind(wx.EVT_CONTEXT_MENU, self.on_show_popup_menu)
        
        # Define events
        wx.EVT_COMBOBOX(self.control_panel.dataset_choice, -1, self.on_dataset_selected)
        wx.EVT_COMBOBOX(self.control_panel.measurement_choice, -1, self.on_measurement_selected)
        wx.EVT_BUTTON(self.control_panel.trajectory_selection_button, -1, self.update_trajectory_selection)
        wx.EVT_COMBOBOX(self.control_panel.colormap_choice, -1, self.on_colormap_selected)
        wx.EVT_BUTTON(self.control_panel.update_plot_button, -1, self.update_plot)
        
    def on_show_all_trajectories(self, event = None):
        all_labels = self.trajectory_info.keys()
        self.trajectory_selection = dict.fromkeys(all_labels,1)
        self.do_plots_need_updating["trajectories"] = True
        self.update_plot()    

    def on_show_popup_menu(self, event = None):   
        '''
        Event handler: show the viewer context menu.  
        
        @param event: the event binder
        @type event: wx event
        '''
        class TrajectoryPopupMenu(wx.Menu):
            '''
            Build the context menu that appears when you right-click on a trajectory
            '''
            def __init__(self, parent):
                super(TrajectoryPopupMenu, self).__init__()
                
                self.parent = parent
            
                # The 'Show data in table' item and its associated binding
                if self.parent.selected_node is not None:
                    item = wx.MenuItem(self, wx.NewId(), "Show data containing %s %s in table"%(props.object_name[0],str(self.parent.selected_node)))
                    self.AppendItem(item)
                    self.Bind(wx.EVT_MENU, self.parent.show_selection_in_table, item)
                    item = wx.MenuItem(self, wx.NewId(), "Show image montage containing %s %s"%(props.object_name[0],str(self.parent.selected_node)))
                    self.AppendItem(item)
                    self.Bind(wx.EVT_MENU, self.parent.show_cell_montage, item)                    
                # The 'Show all trajectories' item and its associated binding
                item = wx.MenuItem(self, wx.NewId(), "Show all trajectories")
                self.AppendItem(item)
                self.Bind(wx.EVT_MENU, self.parent.on_show_all_trajectories, item)

        # The event (mouse right-click) position.
        pos = event.GetPosition()
        # Converts the position to mayavi internal coordinates.
        pos = self.figure_panel.ScreenToClient(pos)                                                        
        # Show the context menu.      
        self.PopupMenu(TrajectoryPopupMenu(self), pos)    

    def show_selection_in_table(self, event = None):
        '''Callback for "Show selection in a table" popup item.'''
        containing_trajectory = [nodes for nodes in self.connected_nodes if self.selected_node in nodes][0]
        keys, ypoints, xpoints, data = zip(*[[self.directed_graph.node[key]["db_key"],key[0],key[1],self.directed_graph.node[key]["s"]] for key in containing_trajectory])
        table_data = np.hstack((np.array(keys), np.array((xpoints,ypoints,data)).T))
        column_labels = list(object_key_columns())
        key_col_indices = list(xrange(len(column_labels)))
        column_labels += [props.object_tracking_label,props.timepoint_id,self.selected_measurement]
        group = 'Object'
        grid = tableviewer.TableViewer(self, title='Trajectory data containing %s %d'%(props.object_name[0],self.selected_node[0]))
        grid.table_from_array(table_data, column_labels, group, key_col_indices)
        # TODO: Confirm that hiding the key columns is actually neccesary. Also, an error gets thrown when the user tries to scrool horizontally.
        grid.grid.Table.set_shown_columns(list(xrange(len(key_col_indices),len(column_labels))))
        grid.set_fitted_col_widths()
        grid.Show()
        
    def show_cell_montage(self, event = None):
        containing_trajectory = [nodes for nodes in self.connected_nodes if self.selected_node in nodes][0]
        keys = [self.directed_graph.node[key]["db_key"] for key in containing_trajectory]
        montage_frame = sortbin.CellMontageFrame(get_main_frame_or_none(),"Image montage containing %s %d"%(props.object_name[0],self.selected_node[0]))
        montage_frame.Show()
        montage_frame.add_objects(keys)
        [tile.Select() for tile in montage_frame.sb.tiles if tile.obKey == self.directed_graph.node[self.selected_node]["db_key"]]
    
    def on_dataset_selected(self, event = None):
        # Disable trajectory selection button until plot updated or the currently plotted dataset is selected
        self.do_plots_need_updating["dataset"] = False
        if self.selected_dataset == self.control_panel.dataset_choice.GetStringSelection():
            self.control_panel.trajectory_selection_button.Enable()
        else:
            self.control_panel.trajectory_selection_button.Disable()
            self.selected_dataset = self.control_panel.dataset_choice.GetStringSelection()
            self.do_plots_need_updating["dataset"] = True
            
    def on_measurement_selected(self, event = None):
        self.do_plots_need_updating["measurement"] = False
        if self.selected_measurement == self.control_panel.measurement_choice.GetStringSelection():
            self.control_panel.trajectory_selection_button.Enable()
        else:
            self.selected_measurement = self.control_panel.measurement_choice.GetStringSelection()            
            self.control_panel.trajectory_selection_button.Disable()  
            self.do_plots_need_updating["measurement"] = True

    def on_colormap_selected(self, event = None):
        self.do_plots_need_updating["colormap"] = False
        if self.selected_colormap != self.control_panel.colormap_choice.GetStringSelection():
            self.selected_colormap = self.control_panel.colormap_choice.GetStringSelection()    
            self.do_plots_need_updating["colormap"] = True
        
    def update_trajectory_selection(self, event = None):
        
        class TrajectoryMultiChoiceDialog (wx.Dialog):
            '''
            Build the dialog box that appears when you click on the trajectory selection
            '''
            def __init__(self, parent, message="", caption="", choices=[]):
                wx.Dialog.__init__(self, parent, -1)
                self.SetTitle(caption)
                sizer1 = wx.BoxSizer(wx.VERTICAL)
                self.message = wx.StaticText(self, -1, message)
                self.clb = wx.CheckListBox(self, -1, choices = choices)
                self.selectallbtn = wx.Button(self,-1,"Select all")
                self.deselectallbtn = wx.Button(self,-1,"Deselect all")
                sizer2 = wx.BoxSizer(wx.HORIZONTAL)
                sizer2.Add(self.selectallbtn,0, wx.ALL | wx.EXPAND, 5)
                sizer2.Add(self.deselectallbtn,0, wx.ALL | wx.EXPAND, 5)
                self.dlgbtns = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
                self.Bind(wx.EVT_BUTTON, self.SelectAll, self.selectallbtn)
                self.Bind(wx.EVT_BUTTON, self.DeselectAll, self.deselectallbtn)
                
                sizer1.Add(self.message, 0, wx.ALL | wx.EXPAND, 5)
                sizer1.Add(self.clb, 1, wx.ALL | wx.EXPAND, 5)
                sizer1.Add(sizer2, 0, wx.EXPAND)
                sizer1.Add(self.dlgbtns, 0, wx.ALL | wx.EXPAND, 5)
                self.SetSizer(sizer1)
                self.Fit()
                
            def GetSelections(self):
                return self.clb.GetChecked()
            
            def SetSelections(self, indexes):
                return self.clb.SetChecked(indexes)

            def SelectAll(self, event):
                for i in range(self.clb.GetCount()):
                    self.clb.Check(i, True)
                    
            def DeselectAll(self, event):
                for i in range(self.clb.GetCount()):
                    self.clb.Check(i, False)
        
        trajectory_selection_dlg = TrajectoryMultiChoiceDialog(self, 
                                                    message = 'Select the objects you would like to show',
                                                    caption = 'Select trajectories to visualize', 
                                                    choices = [str(x) for x in self.trajectory_info.keys()])
                
        current_selection = np.nonzero(self.trajectory_selection.values())[0]
        trajectory_selection_dlg.SetSelections(current_selection)
        
        if (trajectory_selection_dlg.ShowModal() == wx.ID_OK):
            current_selection = trajectory_selection_dlg.GetSelections()
            all_labels = self.trajectory_info.keys()
            self.trajectory_selection = dict.fromkeys(all_labels,0)
            for x in current_selection:
                self.trajectory_selection[all_labels[x]] = 1
            self.do_plots_need_updating["trajectories"] = True
            self.update_plot()                    
    
    def update_plot(self, event = None):
        self.obtain_tracking_data()
        self.generate_graph()
        self.draw_lineage()
        self.draw_trajectories()
        self.control_panel.trajectory_selection_button.Enable()
        self.do_plots_need_updating = {"dataset":False,"colormap":False,"measurement":False, "trajectories":False}
            
    def obtain_tracking_data(self):
        # Only read from database if a new dataset or new measurement is needed
        if self.do_plots_need_updating["dataset"] or self.do_plots_need_updating["measurement"]:
            self.column_names, self.trajectory_info = retrieve_trajectories(self.selected_dataset,self.selected_measurement)
           
    
    def generate_graph(self):
        # Generate the graph relationship if the dataset has been updated
        if self.do_plots_need_updating["dataset"]:           
            logging.info("Retrieved %d %s from dataset %s"%(len(self.trajectory_info),props.object_name[1],self.selected_dataset))
            
            self.directed_graph = nx.DiGraph()
            node_ids = map(itemgetter(0),self.trajectory_info)
            self.directed_graph.add_nodes_from(node_ids)
            
            for current_object in self.trajectory_info.keys():
                node_ids = self.trajectory_info[current_object]["db_key"]
                # Add nodes
                self.directed_graph.add_nodes_from(zip(node_ids,
                                                       [{"x":self.trajectory_info[current_object]["x"][index],
                                                         "y":self.trajectory_info[current_object]["y"][index],
                                                         "t":self.trajectory_info[current_object]["t"][index],
                                                         "label":self.trajectory_info[current_object]["label"][index],
                                                         "s":self.trajectory_info[current_object]["s"][index],
                                                         "parent":self.trajectory_info[current_object]["parent"][index]} for index,item in enumerate(node_ids)]))
                
                # Add edges as list of tuples
                p = nx.get_node_attributes(self.directed_graph,'p') 
                self.directed_graph.add_edges_from([(p[node],node) for node in node_ids if p[node] in node_ids])
                
            # Find start/end nodes by checking for nodes with no outgoing/ingoing edges
            self.start_nodes = [node for (node,value) in self.directed_graph.in_degree().items() if value == 0]
            self.end_nodes = [node for (node,value) in self.directed_graph.out_degree().items() if value == 0]
            
            logging.info("Constructed lineage graph consisting of %d nodes and %d edges"%(self.directed_graph.number_of_nodes(),self.directed_graph.number_of_edges()))
            
            # Hierarchical graph creation: http://stackoverflow.com/questions/11479624/is-there-a-way-to-guarantee-hierarchical-output-from-networkx        
            # Call graphviz to generate the node positional information
            t1 = time.clock()
            node_positions = nx.graphviz_layout(self.directed_graph, prog='dot') 
            t2 = time.clock()
            logging.info("Computed lineage layout (%.2f sec)"%(t2-t1))
            
            # TODO(?): Check into whether I can use arguments into dot to do these spatial flips
            # List of  available graphviz attributes: http://www.graphviz.org/content/attrs        
            p = np.array(node_positions.values())
            p = np.fliplr(p) # Rotate layout from vertical to horizontal
            p[:,0] = np.max(p[:,0])-p[:,0] + np.min(p[:,0])# Flip layout left/right
            for index,key in enumerate(node_positions.keys()):
                node_positions[key] = (p[index,0],p[index,1]) 
            
            # Problem: Since the graph is a dict, the order the nodes are added is not preserved. This is not
            # a problem until the graph is drawn; graphviz orders the root nodes by the node order in the graph object.
            # We want the graph to be ordered by object number.
            # Using G.add_nodes_from or G.subgraph using an ordered dict doesn't solve this.
            # There are a couple of webpages on this issue, which doesn't seem like it will be addressed anytime soon:
            #  https://networkx.lanl.gov/trac/ticket/445
            #  https://networkx.lanl.gov/trac/ticket/711
            
            # So we need to reorder y-locations by the label name.
            # Also, graphviz places the root node at t = 0 for all trajectories. We need to offset the x-locations by the actual timepoint.
            
            connected_nodes = nx.connected_component_subgraphs(self.directed_graph.to_undirected()) #[sorted(nodes) for nodes in sorted(nx.connected_components(self.directed_graph.to_undirected()))]
            self.connected_nodes = dict(zip(range(1,len(connected_nodes)+1),connected_nodes))
            y_min = dict.fromkeys(self.connected_nodes.keys(), np.inf)
            y_max = dict.fromkeys(self.connected_nodes.keys(), -np.inf)
            for (key,trajectory) in self.connected_nodes.items():
                pos = [node_positions[node][1] for node in trajectory.nodes()]
                y_min[key] = min(pos)
                y_max[key] = max(pos)       

            # Assuming that the x-location on the graph for a given timepoint is unique, collect and sort them so they can be mapped into later
            node_x_locs = sorted(np.unique([pos[0] for pos in node_positions.values()]))
            
            # Adjust the y-spacing between trajectories so it the plot is roughly square, to avoid nasty Mayavi axis scaling issues later
            # See: http://stackoverflow.com/questions/13015097/how-do-i-scale-the-x-and-y-axes-in-mayavi2
            # Set the x-origin to give room for the labels
            origin_x = 0 #round(1.0*np.diff(node_x_locs)[0])
            origin_y = origin_x
            spacing_y = round( (max(node_x_locs) - min(node_x_locs))/len(self.end_nodes) )
            offset_y = 0
            for (key,trajectory) in self.connected_nodes.items():
                dy = y_max[key] - y_min[key]
                for node in trajectory.nodes():
                    node_positions[node] = (node_x_locs[self.directed_graph.node[node]["t"]-1] + origin_x, origin_y + offset_y) # (pos[frame][0], origin + offset)
                offset_y += dy + spacing_y
            
            self.lineage_node_positions = node_positions
            self.lineage_node_x_locations = node_x_locs
            
            # When visualizing a new dataset, select all trajectories by default
            self.trajectory_selection = dict.fromkeys(self.trajectory_info.keys(),1)              
        else:
            for current_object in self.trajectory_info.keys():
                t = self.trajectory_info[current_object]["t"]
                s = self.trajectory_info[current_object]["s"]
                for current_scalar, current_time in zip(s,t):
                    self.directed_graph.node[self.trajectory_info[current_object]["db_key"]]["s"] = current_scalar
            
        self.scalar_data = np.array([self.directed_graph.node[key]["s"] for key in sorted(self.directed_graph)])

    def on_pick_one_timepoint(self,picker):
        """ Picker callback: this gets called upon pick events.
        """
        # Retrieving the data from Mayavi pipelines: http://docs.enthought.com/mayavi/mayavi/data.html#retrieving-the-data-from-mayavi-pipelines
        # More helpful example: http://docs.enthought.com/mayavi/mayavi/auto/example_select_red_balls.html
        if picker.actor in self.lineage_node_collection.actor.actors + self.lineage_edge_collection.actor.actors:
            # TODO: Figure what the difference is between node_collection and edge_collection being clicked on.
            # Retrieve to which point corresponds the picked point. 
            # Here, we grab the points describing the individual glyph, to figure
            # out how many points are in an individual glyph.                
            n_glyph = self.lineage_node_collection.glyph.glyph_source.glyph_source.output.points.to_array().shape[0]
            # Find which data point corresponds to the point picked:
            # we have to account for the fact that each data point is
            # represented by a glyph with several points      
            point_id = picker.point_id/n_glyph
            x_lineage,y_lineage,_ = self.lineage_node_collection.mlab_source.points[point_id,:]
            picked_node = sorted(self.directed_graph)[point_id]
            x_traj,y_traj,t_traj = self.trajectory_node_collection.mlab_source.points[point_id,:]
            if picked_node == self.selected_node:
                self.selected_node = None 
            else:
                self.selected_node = picked_node
                
        elif picker.actor in self.trajectory_node_collection.actor.actors:
            n_glyph = self.trajectory_node_collection.glyph.glyph_source.glyph_source.output.points.to_array().shape[0]  
            point_id = picker.point_id/n_glyph            
            x_traj,y_traj,t_traj = self.trajectory_node_collection.mlab_source.points[point_id,:]
            l = self.trajectory_labels[point_id]
            self.selected_trajectories = l
            picked_node = sorted(self.directed_graph)[point_id]
            x_lineage,y_lineage,_ = self.lineage_node_collection.mlab_source.points[point_id,:]
            # If the node was already picked, then deselect it
            if picked_node == self.selected_node:
                self.selected_node = None
                self.selected_trajectories = None
            else:
                self.selected_node = picked_node  
                
        else:
            self.selected_node = None  
            self.selected_trajectories = None

        # If the picked node is not one of the selected trajectories, then don't select it 
        if self.selected_node != None and self.selected_node in self.connected_nodes[self.selected_trajectories].nodes():
            # Move the outline to the data point
            s = 10
            self.lineage_selection_outline.bounds = (x_lineage-s, x_lineage+s,
                                                     y_lineage-s, y_lineage+s,
                                                     0, 0)
            self.lineage_selection_outline.actor.actor.visibility = 1
            s = 3
            self.trajectory_selection_outline.bounds = (x_traj-s, x_traj+s,
                                                        y_traj-s, y_traj+s,
                                                        t_traj-s, t_traj+s)
            self.trajectory_selection_outline.actor.actor.visibility = 1
        else:
            self.selected_node = None  
            self.selected_trajectories = None            
    
    def draw_lineage(self):
        # Rendering temporarily disabled
        self.mayavi_view.lineage_scene.disable_render = True 

        # (Possibly) Helpful pages on using NetworkX and Mayavi:
        # http://docs.enthought.com/mayavi/mayavi/auto/example_delaunay_graph.html
        # https://groups.google.com/forum/?fromgroups=#!topic/networkx-discuss/wdhYIPeuilo
        # http://www.mail-archive.com/mayavi-users@lists.sourceforge.net/msg00727.html        

        # Draw the lineage tree if the dataset has been updated
        if self.do_plots_need_updating["dataset"]:
            # Clear the scene
            logging.info("Drawing lineage graph...")
            self.mayavi_view.lineage_scene.mlab.clf(figure = self.mayavi_view.lineage_scene.mayavi_scene)
            
            #mlab.title("Lineage tree",size=2.0,figure=self.mayavi_view.lineage_scene.mayavi_scene)   
            
            t1 = time.clock()
            
            G = nx.convert_node_labels_to_integers(self.directed_graph,ordering="sorted")
            xys = np.array([self.lineage_node_positions[key]+(self.directed_graph.node[key]["s"],) for key in sorted(self.directed_graph)])
            pts = mlab.points3d(xys[:,0], xys[:,1], np.zeros_like(xys[:,0]), xys[:,2],
                                scale_factor = 10.0, # scale_factor = 'auto' results in huge pts: pts.glyph.glpyh.scale_factor = 147
                                line_width = 0.5, 
                                scale_mode = 'none',
                                colormap = self.selected_colormap,
                                resolution = 8,
                                figure = self.mayavi_view.lineage_scene.mayavi_scene) 
            pts.glyph.color_mode = 'color_by_scalar'
            pts.mlab_source.dataset.lines = np.array(G.edges())

            self.lineage_node_collection = pts
            
            tube = mlab.pipeline.tube(pts, 
                                      tube_radius = 2.0, # Default tube_radius results in v. thin lines: tube.filter.radius = 0.05
                                      figure = self.mayavi_view.lineage_scene.mayavi_scene)
            self.lineage_edge_collection = mlab.pipeline.surface(tube, 
                                                                 color=(0.8, 0.8, 0.8),
                                                                 figure = self.mayavi_view.lineage_scene.mayavi_scene)
            
            # Add object label text to the left
            dx = np.diff(self.lineage_node_x_locations)[0]
            x = [self.lineage_node_positions[node][0]-0.75*dx for node in self.start_nodes]
            y = [self.lineage_node_positions[node][1] for node in self.start_nodes]
            z = list(np.array(y)*0)
            s = [str(self.directed_graph.node[node]["label"]) for node in self.start_nodes]
            self.lineage_label_collection = [mlab.text3d(*xyzs,
                                                         line_width = 20,
                                                         scale = 20,
                                                         figure = self.mayavi_view.lineage_scene.mayavi_scene) 
                                             for xyzs in zip(x,y,z,s)] 
            
            
            # Add outline to be used later when selecting points
            self.lineage_selection_outline = mlab.outline(line_width=3,
                                                          figure = self.mayavi_view.lineage_scene.mayavi_scene)
            self.lineage_selection_outline.outline_mode = 'cornered'
            self.lineage_selection_outline.actor.actor.visibility = 0
            
            # Add axes outlines
            extent = np.array(self.lineage_node_positions.values())
            extent = (0,np.max(extent[:,0]),0,np.max(extent[:,1]),0,0)
            mlab.pipeline.outline(self.lineage_node_collection,
                                  extent = extent,
                                  opacity = self.axes_opacity,
                                  figure = self.mayavi_view.lineage_scene.mayavi_scene) 
            mlab.axes(self.lineage_node_collection, 
                      xlabel='T', ylabel='',
                      extent = extent,
                      opacity = self.axes_opacity,
                      x_axis_visibility=True, y_axis_visibility=False, z_axis_visibility=False)             
            self.mayavi_view.lineage_scene.reset_zoom()
            
            # Constrain view to 2D
            self.mayavi_view.lineage_scene.interactor.interactor_style = tvtk.InteractorStyleImage()
            
            # Make the graph clickable
            self.mayavi_view.lineage_scene.mayavi_scene.on_mouse_pick(self.on_pick_one_timepoint)
    
            t2 = time.clock()
            logging.info("Computed layout (%.2f sec)"%(t2-t1))   
        else:
            logging.info("Re-drawing lineage tree...")
            
            if self.do_plots_need_updating["trajectories"]:
                # Alter lines between the points that we have previously created by
                # directly modifying the VTK dataset.                
                nodes_to_remove = [self.connected_nodes[index] for index,val in enumerate(self.trajectory_selection.values()) if val == 0]
                nodes_to_remove = [item for sublist in nodes_to_remove for item in sublist]
                mapping = dict(zip(sorted(self.directed_graph),range(0,self.directed_graph.number_of_nodes()+1)))
                nodes_to_remove = [mapping[item] for item in nodes_to_remove]
                G = nx.relabel_nodes(self.directed_graph, mapping, copy=True)
                G.remove_nodes_from(nodes_to_remove)
                self.lineage_node_collection.mlab_source.dataset.lines = np.array(G.edges())
                self.lineage_node_collection.mlab_source.update()
                #self.lineage_edge_collection.mlab_source.dataset.lines = np.array(G.edges())
                #self.lineage_edge_collection.mlab_source.update()
                
                for index,item in enumerate(self.lineage_label_collection):
                    item.actor.actor.visibility = self.trajectory_selection[index+1]                
                
            if self.do_plots_need_updating["measurement"]:
                self.lineage_node_collection.mlab_source.set(scalars = self.scalar_data)
            
            if self.do_plots_need_updating["colormap"]:
                # http://docs.enthought.com/mayavi/mayavi/auto/example_custom_colormap.html
                self.lineage_node_collection.module_manager.scalar_lut_manager.lut_mode = self.selected_colormap
                
        # Re-enable the rendering
        self.mayavi_view.lineage_scene.disable_render = False

    def draw_trajectories(self):
        # Rendering temporarily disabled
        self.mayavi_view.trajectory_scene.disable_render = True  
        
        # Draw the lineage tree if either (1) all the controls indicate that updating is needed (e.g., initial condition) or
        # (2) if the dataset has been updated        
        if self.do_plots_need_updating["dataset"]:

            logging.info("Drawing trajectories...")
            # Clear the scene
            self.mayavi_view.trajectory_scene.mlab.clf(figure = self.mayavi_view.trajectory_scene.mayavi_scene)
    
            #mlab.title("Trajectory plot",size=2.0,figure=self.mayavi_view.trajectory_scene.mayavi_scene)   
    
            t1 = time.clock()
            
            G = nx.convert_node_labels_to_integers(self.directed_graph,ordering="sorted")
    
            xyts = np.array([(self.directed_graph.node[key]["x"],
                              self.directed_graph.node[key]["y"],
                              self.directed_graph.node[key]["t"],
                              self.directed_graph.node[key]["s"]) for key in sorted(self.directed_graph)])
            
            # Compute reasonable scaling factor according to the data limits.
            # We want the plot to be roughly square, to avoid nasty Mayavi axis scaling issues later.
            # Unfortunately, adjusting the surface.actor.actor.scale seems to lead to more problems than solutions.
            # See: http://stackoverflow.com/questions/13015097/how-do-i-scale-the-x-and-y-axes-in-mayavi2
            t_scaling = np.mean( [(max(xyts[:,0])-min(xyts[:,0])), (max(xyts[:,1])-min(xyts[:,1]))] ) / (max(xyts[:,2])-min(xyts[:,2]))
            xyts[:,2] *= t_scaling
    
            # Taken from http://docs.enthought.com/mayavi/mayavi/auto/example_plotting_many_lines.html
            # Create the lines
            self.trajectory_line_source = mlab.pipeline.scalar_scatter(xyts[:,0], xyts[:,1], xyts[:,2], xyts[:,3], \
                                                                       figure = self.mayavi_view.trajectory_scene.mayavi_scene)
            # Connect them
            self.trajectory_line_source.mlab_source.dataset.lines = np.array(G.edges())     
            
            # Finally, display the set of lines by using the surface module. Using a wireframe
            # representation allows to control the line-width.
            self.trajectory_line_collection = mlab.pipeline.surface(mlab.pipeline.stripper(self.trajectory_line_source), # The stripper filter cleans up connected lines; it regularizes surfaces by creating triangle strips
                                                                    line_width=1, 
                                                                    colormap=self.selected_colormap,
                                                                    figure = self.mayavi_view.trajectory_scene.mayavi_scene)         
    
            self.trajectory_labels = np.array([self.directed_graph.node[key]["label"] for key in sorted(self.directed_graph)])
            
            # Generate the corresponding set of nodes
            pts = mlab.points3d(xyts[:,0], xyts[:,1], xyts[:,2], xyts[:,3],
                                scale_factor = 0.0, # scale_factor = 'auto' results in huge pts: pts.glyph.glpyh.scale_factor = 147
                                scale_mode = 'none',
                                colormap = self.selected_colormap,
                                figure = self.mayavi_view.trajectory_scene.mayavi_scene) 
            pts.glyph.color_mode = 'color_by_scalar'
            pts.mlab_source.dataset.lines = np.array(G.edges())
            self.trajectory_node_collection = pts    
    
            # Add object label text
            self.trajectory_label_collection = [mlab.text3d(self.directed_graph.node[sorted(subgraph)[-1]]["x"],
                                                            self.directed_graph.node[sorted(subgraph)[-1]]["y"],
                                                            self.directed_graph.node[sorted(subgraph)[-1]]["t"]*t_scaling,
                                                            str(key),
                                                            line_width = 20,
                                                            scale = 10,
                                                            name = str(key),
                                                            figure = self.mayavi_view.trajectory_scene.mayavi_scene) 
                                                for (key,subgraph) in self.connected_nodes.items()]
            
            # Add outline to be used later when selecting points
            self.trajectory_selection_outline = mlab.outline(line_width = 3,
                                                             figure = self.mayavi_view.trajectory_scene.mayavi_scene)
            self.trajectory_selection_outline.outline_mode = 'cornered'
            self.trajectory_selection_outline.actor.actor.visibility = 0
            
            # Using axes doesn't work until the scene is avilable: 
            # http://docs.enthought.com/mayavi/mayavi/building_applications.html#making-the-visualization-live
            mlab.pipeline.outline(self.trajectory_line_source,
                                  opacity = self.axes_opacity,
                                  figure = self.mayavi_view.trajectory_scene.mayavi_scene) 
            mlab.axes(self.trajectory_line_source, 
                      xlabel='X', ylabel='Y',zlabel='T',
                      opacity = self.axes_opacity,
                      x_axis_visibility=True, y_axis_visibility=True, z_axis_visibility=True) 
            # Set axes to MATLAB's default 3d view
            mlab.view(azimuth = 322.5,elevation = 30.0,
                      figure = self.mayavi_view.trajectory_scene.mayavi_scene)
            self.mayavi_view.trajectory_scene.reset_zoom()
            
            # An trajectory picker object is created to trigger an event when a trajectory is picked.       
            # TODO: Figure out how to re-activate picker on scene refresh
            #  E.g., (not identical problem) http://www.mail-archive.com/mayavi-users@lists.sourceforge.net/msg00583.html
            picker = self.mayavi_view.trajectory_scene.mayavi_scene.on_mouse_pick(self.on_pick_one_timepoint)
            picker.tolerance = 0.01
            
            # Figure decorations
            # Orientation axes
            #mlab.orientation_axes(zlabel = "T", 
                                  #line_width = 5,
                                  #figure = self.mayavi_view.trajectory_scene.mayavi_scene )
            # Colormap
            # TODO: Figure out how to scale colorbar to smaller size
            #c = mlab.colorbar(orientation = "horizontal", 
                              #title = self.selected_measurement,
                              #figure = self.mayavi_view.trajectory_scene.mayavi_scene)
            #c.scalar_bar_representation.position2[1] = 0.05
            #c.scalar_bar.height = 0.05
            
            t2 = time.clock()
            logging.info("Computed trajectory layout (%.2f sec)"%(t2-t1))              
        else:
            logging.info("Re-drawing trajectories...")
            
            if self.do_plots_need_updating["trajectories"]:
                # Alter lines between the points that we have previously created by
                # directly modifying the VTK dataset.                
                nodes_to_remove = [self.connected_nodes[index] for index,val in enumerate(self.trajectory_selection.values()) if val == 0]
                nodes_to_remove = [item for sublist in nodes_to_remove for item in sublist]
                mapping = dict(zip(sorted(self.directed_graph),range(0,self.directed_graph.number_of_nodes()+1)))
                nodes_to_remove = [mapping[item] for item in nodes_to_remove]
                G = nx.relabel_nodes(self.directed_graph, mapping, copy=True)
                G.remove_nodes_from(nodes_to_remove)
                self.trajectory_line_collection.mlab_source.dataset.lines = np.array(G.edges())
                self.trajectory_line_collection.mlab_source.update()
                self.trajectory_line_source.mlab_source.dataset.lines = np.array(G.edges())
                self.trajectory_line_source.mlab_source.update()
                
                for index,item in enumerate(self.trajectory_label_collection):
                    item.actor.actor.visibility = self.trajectory_selection[index+1]

            if self.do_plots_need_updating["measurement"]:
                self.trajectory_line_collection.mlab_source.set(scalars = self.scalar_data)
                self.trajectory_node_collection.mlab_source.set(scalars = self.scalar_data)
            
            if self.do_plots_need_updating["colormap"]:
                self.trajectory_line_collection.module_manager.scalar_lut_manager.lut_mode = self.selected_colormap
                self.trajectory_node_collection.module_manager.scalar_lut_manager.lut_mode = self.selected_colormap
                
        # Re-enable the rendering
        self.mayavi_view.trajectory_scene.disable_render = False  

################################################################################
if __name__ == "__main__":
        
    import sys
    app = wx.PySimpleApp()
    logging.basicConfig(level=logging.DEBUG,)

    # Load a properties file if passed in args
    if len(sys.argv) > 1:
        propsFile = sys.argv[1]
        props.LoadFile(propsFile)
        props = add_props_field(props)
    else:
        if not props.show_load_dialog():
            print 'Time Visualizer requires a properties file.  Exiting.'
            # Necessary in case other modal dialogs are up
            wx.GetApp().Exit()
            sys.exit()
        else:
            props = add_props_field(props)
            
    timelapsevisual = TimeLapseTool(None)
    timelapsevisual.Show()

    app.MainLoop()
    
    #
    # Kill the Java VM
    #
    try:
        from bioformats import jutil
        jutil.kill_vm()
    except:
        import traceback
        traceback.print_exc()
        print "Caught exception while killing VM"
