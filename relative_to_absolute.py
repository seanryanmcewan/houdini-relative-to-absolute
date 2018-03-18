from hutil.Qt import QtCore
from hutil.Qt import QtWidgets

class relative_to_absolute(QtWidgets.QWidget):
    """
    Checks all parameters of the specified nodes for relative file references, and converts them to absolute file references. 
    
    For example: "$HIP/geo/my_cache.bgeo" would be converted to "/path/to/your/hip/geo/my_cache.bgeo"
    It will also follow channel references to find relative file references. 
    For example:
    The 'file' parameter of file_node1 is set to "$HIP/geo/my_cache.bgeo"
    The 'file' parameter of file_node2 is set to `chs("../file1/file")`
    
    If run on file_node2, its file parameter will be expanded to "/path/to/your/hip/geo/my_cache.bgeo"
    """
    
    def __init__(self, parent=None):
        # INITIALIZE GUI AND SET WINDOW TO ALWAYS ON TOP
        QtWidgets.QWidget.__init__(self, parent, QtCore.Qt.WindowStaysOnTopHint)
        
        # SET LAYOUTS
        vbox = QtWidgets.QVBoxLayout()
        hbox1 = QtWidgets.QHBoxLayout()        
        
        # SET WINDOW ATTRIBUTES
        self.setGeometry(500, 300, 420, 110)
        self.setWindowTitle('Convert Relative File Paths to Absolute')
        
        # CREATE WIDGETS
        self.apply_to_label = QtWidgets.QLabel("Nodes to Update:")
        self.apply_to_combo_box = QtWidgets.QComboBox(self)     
        self.update_paths_button = QtWidgets.QPushButton('Update Paths', self)
        
        # POPULATE COMBO BOX
        self.apply_to_combo_box.addItem("Selected Nodes Only")        
        self.apply_to_combo_box.addItem("All Nodes In Scene (Any Context)")          
        self.apply_to_combo_box.addItem("All Nodes In Obj Context")           
        self.apply_to_combo_box.addItem("Selected Nodes & Their Direct Children")
        self.apply_to_combo_box.addItem("Selected Nodes & All Subchildren")        
        self.apply_to_combo_box.addItem("Only Direct Children Of Selected Nodes")   
        self.apply_to_combo_box.addItem("Only All Subchildren Of Selected Nodes")           

        # CONNECT BUTTONS TO FUNCTIONS
        self.update_paths_button.clicked.connect(self.updatePaths)
        
        # ADD WIDGETS TO LAYOUT
        hbox1.addWidget(self.apply_to_label) 
        hbox1.addWidget(self.apply_to_combo_box)     
        vbox.addLayout(hbox1)
        vbox.addWidget(self.update_paths_button)
        
        # SET LAYOUT
        self.setLayout(vbox)
        

    def updatePaths(self):  
        """
        Iterates over all of the external file references in the current scene, and sends the containing parameter 
        to the 'checkBeforeChange' method.
        """
        
        self.updated_list = []
        
        # QUERY USER ON WHICH NODES TO APPLY TO
        sels = self.setSearchMode(hou.selectedNodes())     
        
        # FIND AND ITERATE OVER ALL EXTERNAL FILE REFERENCES IN SCENE
        refs =  hou.fileReferences()
        for ref in refs:
            if ref[0]:
                
                # IF NODE CONTAINING PARAMETER IS NOT INSIDE LOCKED HDA AND NODE IS QUERIED BY USER, UPDATE PARAMETER
                if not ref[0].node().isInsideLockedHDA():
                        if ref[0].node() in sels: 
                            self.checkBeforeChange(ref[0])
                            
                # IF NODE CONTAINING PARAMETER IS INSIDE LOCKED HDA
                else:  
                    
                    # FIND NEXT PARENT WHICH IS NOT A LOCKED HDA
                    unlocked_parent = ref[0].node()
                    x = 0
                    while x < 20:
                        if not unlocked_parent.isInsideLockedHDA():
                            break
                        unlocked_parent = unlocked_parent.parent()
                        x += 1
                        
                    # CHECK IF UNLOCKED PARENT IS QUERIED BY USER
                    for sel in sels:
                        if unlocked_parent.path() in sel.path():
                            for parm in unlocked_parent.parms():
                                
                                    # IF PARM IS LINKED TO ANOTHER PARM, UPDATE PARM
                                    if parm.getReferencedParm() != parm:
                                        self.checkBeforeChange(parm)
                                        
                                    # IF PARM IS NOT LINKED TO ANOTHER PARM, MAKE SURE IT IS A STRING PARM
                                    elif type(parm.parmTemplate()) is hou.StringParmTemplate:
                                        
                                        # IF VALUE MATCHES EXTERNAL REFERENCES, UPDATE PARM
                                        if parm.unexpandedString() == ref[1]:
                                            self.checkBeforeChange(parm)
          
        # IF ANYTHING WAS CHANGED, DISPLAY A POP-UP LISTING THE CHANGES
        if self.updated_list:
            message = "The following paths were updated:\n"
            for item in self.updated_list:
                message += '\nThe parm "{0}" was changed from/to:\n{1}\n{2}\n'.format(item[0], item[1],item[2])
            hou.ui.displayMessage(message)
         
        
    def checkBeforeChange(self, p):
        """
        Determines whether a parameter can be updated, then sends to the 'relativeToAbsolute' method.
        
        Arguments:
        p (hou.Parm): Houdini parameter to check.
        """
        
        # CAN'T GET UNEXPANDEDSTRING FOR PARMS WITH KEYFRAMES
        if not p.keyframes():  
                    
            # CHECK IF IT'S A COMPLICATED EXPRESSION
            if p.unexpandedString().count('"') > 2 or p.unexpandedString().count("'") > 2:
                
                # A HACKY WAY TO DEAL WITH EXPRESSIONS WITHIN EXPRESSIONS. MAY NEED TO UPDATE ON CASE-BY-CASE BASIS, BUT WORKS WITH WHAT I'VE THROWN AT IT SO FAR
                old_p_val = p.unexpandedString()
                linked_node = p.unexpandedString().lstrip('`chs(').rstrip(')`')
                quote_style = linked_node[0]
                linked_parm = linked_node.rpartition('/')[-1].rstrip('"').rstrip("'")     
                linked_node = linked_node.rpartition('/')[0]
                p.set('`opfullpathfrom({0}{1}, {2}{3}")`'.format(linked_node, quote_style, quote_style, p.node().path()))
                ref_parm = hou.parm(p.eval() + "/" + linked_parm)
                p.revertToDefaults()
                new_p_val = self.relativeToAbsolute(ref_parm, p)
                if old_p_val != new_p_val:
                    self.updated_list.append([p.path(), old_p_val, new_p_val])   
                    
            # MAKE SURE PARM ISN'T REFERENCING ANOTHER NODE
            elif p.getReferencedParm() == p:
                old_p_val = p.unexpandedString()
                new_p_val = self.relativeToAbsolute(p,p)
                if old_p_val != new_p_val:
                    self.updated_list.append([p.path(), old_p_val, new_p_val])
                    
            #IF IT IS, EVALUATE THE PARAMETER ON THE OTHER NODE
            else:
                old_p_val = p.unexpandedString()
                ref_parm = p.getReferencedParm()
                p.revertToDefaults()                                
                new_p_val = self.relativeToAbsolute(ref_parm, p)
                if old_p_val != new_p_val:
                    self.updated_list.append([p.path(), old_p_val, new_p_val])   


    def relativeToAbsolute(self, parm_to_read, parm_to_set):  
        """
        Converts a parameter from a relative reference to an absolute references, while maintaining
        frame variables (i.e. $F, $FF, $F4).
        
        Arguments:
        parm_to_read (hou.Parm): Houdini parameter to convert references from.
        parm_to_set (hou.Parm): Houdini parameter to set updated value on.
        
        Returns:
        new_val_finalized: Updated value for parameter.
        """
        
        # INITIALIZE VARIABLES
        old_parm_to_read_val = parm_to_read.unexpandedString()
        ue = parm_to_read.unexpandedString()
        index_list = []
        index_update = 0
        
        # CHECK IF ANY FRAME VARIABLES BEING USED
        if "$F" in ue:
            n = 0
            
            # BUILD LIST OF FRAME VARIABLE INDEXES
            for ch in ue:
                if ue[n:n+2] == "$F":
                    index_list.append(n)
                n += 1
                
            # ITERATATE OVER EACH FRAME VARIABLE INDEX
            for index in index_list:
                x = 0    
                
                # IF VARIABLE IS $FPS, $FSTART, OR $FEND, IGNORE
                if ue[index+2:index+4] == "PS" or ue[index+2:index+5] == "END" or ue[index+2:index+7] == "START":
                    pass
                
                # HANDLE IF VARIABLE IS $FF
                elif ue[index+2:index+3] == "F":
                    index += index_update
                    temp = "~~~TEMPORARY_HOLDING_FOR_FRAME___FF"
                    index_update += (len(temp) - len("$FF"))
                    new_val = parm_to_read.unexpandedString()[:index] + \
                    parm_to_read.unexpandedString()[index:index+3].replace(parm_to_read.unexpandedString()[index:index+3], temp) + \
                    parm_to_read.unexpandedString()[index+3:]
                    parm_to_read.set(new_val)
                    
                # HANDLE $F AND ANY TRAILING DIGITS
                else:
                    switch = 1           
                    while switch:
                        try:
                            int(ue[index+2+x])
                        except:
                            switch = 0
                        x += 1
                    index += index_update
                    temp = "~~~TEMPORARY_HOLDING_FOR_FRAME___{0}".format(parm_to_read.unexpandedString()[index:index+2+x-1].lstrip("$"))
                    index_update += (len(temp) - len(parm_to_read.unexpandedString()[index:index+2+x-1]))
                    new_val = parm_to_read.unexpandedString()[:index] + \
                    parm_to_read.unexpandedString()[index:index+2+x-1].replace(parm_to_read.unexpandedString()[index:index+2+x-1], temp) + \
                    parm_to_read.unexpandedString()[index+2+x-1:]
                    parm_to_read.set(new_val)                    
         
        # CLEAN UP AND SET PARAMETER TO NEW VALUE
        new_val = parm_to_read.eval()
        parm_to_read.set(old_parm_to_read_val)
        parm_to_set.set(new_val)
        new_val_finalized = parm_to_set.eval().replace("~~~TEMPORARY_HOLDING_FOR_FRAME___","$")
        parm_to_set.set(new_val_finalized) 
        
        
        return new_val_finalized
        
    def setSearchMode(self, current_selection):
        """
        Query user for which nodes to apply to (reads from "Apply To" combobox)
        
        Arguments:
        current_selection (int): Determines which nodes will queried. Options are:
            0 - Selected Nodes Only
            1 - All Nodes In Scene (Any Context)
            2 - All Nodes In Obj Context
            3 - Selected Nodes And Their Direct Children
            4 - Selected Nodes And All Subchildren
            5 - Only Direct Children of Selected Nodes
            6 - Only All Subchildren Of Selected Nodes
            
        Returns:
        sel (list): list of nodes to query
        """
        
        search_mode = self.apply_to_combo_box.currentIndex() 
        sel = []
        
        # SELECTED NODES ONLY
        if search_mode == 0:
            sel = current_selection    
            
        # ALL NODES IN SCENE (ANY CONTEXT)
        elif search_mode == 1:
            for node in hou.node('/').allSubChildren():
                if "/obj/ipr_camera" not in node.path():
                    sel.append(node)   
                    
        # ALL NODES IN OBJ CONTEXT
        elif search_mode == 2:
            for node in hou.node('/obj').allSubChildren():
                if "/obj/ipr_camera" not in node.path():
                    sel.append(node)          
                    
        # SELECTED NODES AND DIRECT CHILDREN
        elif search_mode == 3:
            for node in current_selection:
                if node.children():
                    sel.extend(list(node.children()))   
            sel.extend(current_selection)
            
        # SELECTED NODES & ALL SUBCHILDREN
        elif search_mode == 4:
            sel = current_selection
            for node in current_selection:
                if node.children():
                    sel.extend(list(node.allSubChildren()))
                    
        # ONLY DIRECT CHILDREN OF SELECTED NODES
        elif search_mode == 5:
            for node in current_selection:
                if node.children():
                    sel.extend(list(node.children())) 
                    
        # ONLY ALL SUBCHILDREN OF SELECTED NODES
        elif search_mode == 6:
            for node in current_selection:
                if node.children():
                    sel.extend(node.allSubChildren())   
        
        return sel       
    
    
                
dialog = relative_to_absolute()
dialog.show()
