# -*- coding: utf-8 -*-
# Cursor Movements
# Copyright (C) 20023
# Version 6.1.1
# License GNU GPL
# Date: 05/05/2022
# Author: Karl-Otto Rosenqvist
# Use predefined mouse cursor movements to be able to create screen recordings for demos and support purposes.


import threading
import os
from configobj import ConfigObj
import globalPluginHandler
import inputCore
import gui
import wx
import config
import globalVars
import scriptHandler
import mouseHandler
import ui
import api
import winUser
import addonHandler
import time
import math as np
import random


addonHandler.initTranslation()

sqrt3 = np.sqrt(3)
sqrt5 = np.sqrt(5)

# Each global constant is prefixed with "CM".

# Constants
CMMousePositions = os.path.join(globalVars.appArgs.configPath, "addons", "cursormovements", "mousePositions")
# Mouse movement directions
shortCut = "none"


# Reports mouse position, used in various places.
def reportMousePosition(x=None, y=None):
	# The coordinates are keywords so specific position can be announced if needed.
	cursorPos = winUser.getCursorPos()
	if x is None:
		x = cursorPos[0]
	if y is None:
		y = cursorPos[1]
	ui.message("{0}, {1}".format(x, y))


def setMousePosition(x, y, announceMousePosition=False, click=False):
	# Setter version of report mouse position function.
	# The new position announcement is to be used if needed.
	winUser.setCursorPos(x, y)
	mouseHandler.executeMouseMoveEvent(x, y)
	if click:
		winUser.mouse_event(winUser.MOUSEEVENTF_LEFTDOWN, 0, 0, None, None)
		winUser.mouse_event(winUser.MOUSEEVENTF_LEFTUP, 0, 0, None, None)
		#wx.CallLater(100, ui.message, _("left click"))
	if announceMousePosition:
		# Announce this half a second later to give the appearance of mouse movement.
		wx.CallLater(500, reportMousePosition, x=x, y=y)


class EnterPositionName(wx.TextEntryDialog):
	"""
	This subclass of the wx.TextEntryDialog class was created to
	prevent multiple instances of the dialog box that propose to give a name to the current mouse position.
	This dialog can be opened via the script_saveMousePosition accessible with the nvda+shift+l shortcut.
	"""
	# The following comes from exit dialog class from GUI package (credit: NV Access and Zahari from Bulgaria).
	_instance = None

	def __new__(cls, parent, *args, **kwargs):
		inst = cls._instance() if cls._instance else None
		if not inst:
			return super(cls, cls).__new__(cls, parent, *args, **kwargs)
		return inst

	def __init__(self, *args, **kwargs):
		inst = EnterPositionName._instance() if EnterPositionName._instance else None
		if inst:
			return
		# Use a weakref so the instance can die.
		import weakref
		EnterPositionName._instance = weakref.ref(self)

		super(EnterPositionName, self).__init__(*args, **kwargs)


class PositionsList(wx.Dialog):
	"""
	This common dialogue has been created to facilitate access to the following choices:
	1. The list of x / y positions proposed by the script_goToPosition,
J	accessible via the nvda+windows+j shortcut.
	2. The list of mouse positions saved for the current application proposed by the script_mousePositionsList,
	accessible via the nvda+control+l shortcut.
	It also prevents multiple instances for these 2 dialogs.
	"""
	# The following comes from exit dialog class from GUI package (credit: NV Access and Zahari from Bulgaria).
	_instance = None

	def __new__(cls, parent, *args, **kwargs):
		inst = cls._instance() if cls._instance else None
		if not inst:
			return super(cls, cls).__new__(cls, parent, *args, **kwargs)
		return inst

	def __init__(self, parent, appName=None, goto=False):
		inst = PositionsList._instance() if PositionsList._instance else None
		if inst:
			return
		# Use a weakref so the instance can die.
		import weakref
		PositionsList._instance = weakref.ref(self)

		if appName:
			super(PositionsList, self).__init__(parent, title=_("Mouse positions for %s") % (appName), size=(420, 300))
			self.mousePositionsList(appName=appName)
		elif goto:
			super(PositionsList, self).__init__(parent, title=_("New mouse position"))
			self.jumpToPosition()

	def mousePositionsList(self, appName):
		self.appName = appName
		self.positions = ConfigObj(os.path.join(CMMousePositions, f"{appName}.cm"), encoding="UTF-8")
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: The label for the list view of the mouse positions in the current application.
		mousePositionsText = _("&Saved mouse positions")
		self.mousePositionsList = sHelper.addLabeledControl(
			mousePositionsText, wx.ListCtrl, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(550, 350)
		)
		self.listItems()
		self.mousePositionsList.Select(0, on=1)
		self.mousePositionsList.SetItemState(0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)

		jumpButtonID = wx.NewIdRef()
		# Translators: the button to jump to the selected position.
		bHelper.addButton(self, jumpButtonID, _("&Jump"), wx.DefaultPosition)

		renameButtonID = wx.NewIdRef()
		# Translators: the button to rename a mouse position.
		bHelper.addButton(self, renameButtonID, _("&Rename"), wx.DefaultPosition)

		setShortCutButtonID = wx.NewIdRef()
		# Translators: the button to set  shortcut for mouse a position.
		bHelper.addButton(self, setShortCutButtonID, _("&add shortcut"), wx.DefaultPosition)

		deleteButtonID = wx.NewIdRef()
		# Translators: the button to delete the selected mouse position.
		bHelper.addButton(self, deleteButtonID, _("&Delete"), wx.DefaultPosition)

		clearButtonID = wx.NewIdRef()
		# Translators: the button to clear all mouse positions for the focused app.
		bHelper.addButton(self, clearButtonID, _("C&lear positions"), wx.DefaultPosition)

		# Translators: The label of a button to close the mouse positions dialog.
		bHelper.addButton(self, wx.ID_CLOSE, _("&Close"), wx.DefaultPosition)

		sHelper.addItem(bHelper)

		self.Bind(wx.EVT_BUTTON, self.onJump, id=jumpButtonID)
		self.Bind(wx.EVT_BUTTON, self.onRename, id=renameButtonID)
		self.Bind(wx.EVT_BUTTON, self.onAdd, id=setShortCutButtonID)
		self.Bind(wx.EVT_BUTTON, self.onDelete, id=deleteButtonID)
		self.Bind(wx.EVT_BUTTON, self.onClear, id=clearButtonID)
		self.Bind(wx.EVT_BUTTON, lambda evt: self.Close(), id=wx.ID_CLOSE)

		# Borrowed from NVDA Core (add-ons manager).
		# To allow the dialog to be closed with the escape key.
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.EscapeId = wx.ID_CLOSE

		mainSizer.Add(sHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.Sizer = mainSizer
		mainSizer.Fit(self)
		self.mousePositionsList.SetFocus()
		self.CenterOnScreen()

	def listItems(self):
		# Translators: the column in mouse positions list to identify the position name.
		self.mousePositionsList.InsertColumn(0, _("Name"), width=150)
		# Translators: the column in mouse positions list to identify the X coordinate.
		self.mousePositionsList.InsertColumn(1, _("Position X"), width=50)
		# Translators: the column in mouse positions list to identify the Y coordinate.
		self.mousePositionsList.InsertColumn(2, _("Position Y"), width=50)
		# Translators: the column in mouse positions list to identify the Shortcut.
		self.mousePositionsList.InsertColumn(3, _("shortCut"), width=100)
		self.mousePositionsList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onJump)
		for entry in self.positions.keys():
			list = self.positions[entry].split(",")
			x = list[0]
			y = list[1]
			try:
				z = list[2]
			except Exception:
				z = "None"
			self.mousePositionsList.Append((entry, x, y, z))

	def jumpToPosition(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mouseJumpHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		x, y = winUser.getCursorPos()
		w, h = api.getDesktopObject().location[2:]
		self.xPos = mouseJumpHelper.addLabeledControl(
			_("&X position"), gui.nvdaControls.SelectOnFocusSpinCtrl, min=0, max=w - 1, initial=x
		)
		self.yPos = mouseJumpHelper.addLabeledControl(
			_("&Y position"), gui.nvdaControls.SelectOnFocusSpinCtrl, min=0, max=h - 1, initial=y
		)

		mouseJumpHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON, self.onCancel, id=wx.ID_CANCEL)
		mainSizer.Add(mouseJumpHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.CenterOnScreen()
		self.xPos.SetFocus()

	def onRename(self, event):
		index = self.mousePositionsList.GetFirstSelected()
		oldName = self.mousePositionsList.GetItemText(index)
		name = wx.GetTextFromUser(
			# Translators: The label of a field to enter a new name for a mouse position/tag.
			_("New name"),
			# Translators: The title of the dialog to rename a mouse position.
			_("Rename"), oldName
		)
		# When escape is pressed, an empty string is returned.
		if name in ("", oldName):
			return
		if name in self.positions:
			gui.messageBox(
				# Translators: An error displayed when renaming a mouse position
				# and a tag with the new name already exists.
				_("Another mouse position has the same name as the entered name. Please choose a different name."),
				_("Error"), wx.OK | wx.ICON_ERROR, self
			)
			return
		self.mousePositionsList.SetItemText(index, name)
		self.mousePositionsList.SetFocus()
		self.positions[name] = self.positions[oldName]
		del self.positions[oldName]

	def onAdd(self, event):
		# Translators: The prompt to enter a gesture
		t = threading.Timer(0.5, ui.message, [_("Enter input gesture:")])
		t.start()
		inputCore.manager._captureFunc = self.addGestureCaptor

	def saveShortCut(self, str):
		global shortCut
		index = self.mousePositionsList.GetFirstSelected()
		name = self.mousePositionsList.GetItemText(index)
		list = self.positions[name].split(",")
		x = list[0]
		y = list[1]
		shortCut = str.split(":")[1]
		shortCut = shortCut.replace("control", "CONTROL")
		if shortCut in [
			"tab", "shift+tab", "upArrow", "downArrow", "leftArrow", "rightArrow", "home", "end", "escape",
			"pageUp", "pageDown", ",", "numpadEnter", "space", "enter"]:
			gui.messageBox(
				# Translators: Message displayde if shortCut is not valid.
				_("This shortCut is not valid, choose another one please"),
				# Translators: Title of message box.
				_("Information"), wx.OK | wx.ICON_INFORMATION
			)
			return
		for k, v in self.positions.items():
			if "," + shortCut in v:
				newV = v.replace("," + shortCut, "")
				self.positions[k] = newV
		self.positions[name] = x + "," + y + "," + shortCut
		self.mousePositionsList.ClearAll()
		self.listItems()
		self.mousePositionsList.Select(index, on=1)
		self.mousePositionsList.SetFocus()
		self.mousePositionsList.SetItemState(index, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
		t = threading.Timer(0.2, ui.message, [_("Shortcut added successfully")])
		t.start()

	def addGestureCaptor(self, gesture: inputCore.InputGesture):
		if gesture.isModifier:
			return False
		inputCore.manager._captureFunc = None
		wx.CallAfter(self.saveShortCut, gesture.identifiers[-1])
		return False

	def deletePosition(self, clearPositions=False):
		message, title = "", ""
		entry = self.mousePositionsList.GetFirstSelected()
		name = self.mousePositionsList.GetItemText(entry)
		if not clearPositions:
			message = _(
				# Translators: The confirmation prompt displayed when the user requests to delete the selected tag.
				"Are you sure you want to delete the position named {name}? This cannot be undone."
			).format(name=name)
			# Translators: The title of the confirmation dialog for deletion of selected position.
			title = _("Delete position")
		else:
			message = _(
				# Translators: The confirmation prompt displayed when the user is about to clear positions.
				"Are you sure you want to clear mouse positions for the current application ({appName})? "
				"This cannot be undone."
			).format(appName=self.appName)
			# Translators: The title of the confirmation dialog for clearing mouse positions.
			title = _("Clear mouse positions")
		if gui.messageBox(
			message, title, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self
		) == wx.NO:
			return
		if not clearPositions:
			del self.positions[name]
			self.mousePositionsList.DeleteItem(entry)
			self.positions.write()
			if self.mousePositionsList.GetItemCount() > 0:
				self.mousePositionsList.Select(0, on=1)
		if clearPositions or self.mousePositionsList.GetItemCount() == 0:
			os.remove(self.positions.filename)
			self.positions.clear()
			gui.messageBox(
				# Translators: A dialog message shown when tags for the application is cleared.
				_("All mouse positions for the application {appName} have been deleted.").format(appName=self.appName),
				# Translators: Title of the tag clear confirmation dialog.
				_("Mouse positions cleared"), wx.OK | wx.ICON_INFORMATION
			)
			self.Close()

	def onDelete(self, event):
		self.deletePosition()

	def onClear(self, event):
		self.deletePosition(clearPositions=True)

	def onJump(self, event):
		index = self.mousePositionsList.GetFirstSelected()
		name = self.mousePositionsList.GetItemText(index)
		list = self.positions[name].split(",")
		self.Destroy()
		self.positions.write()
		try:
			x, y = list[0], list[1]
		except Exception:
			return
		self.positions = None
		wx.CallLater(500, setMousePosition, int(x), int(y))

	def onClose(self, evt):
		self.Destroy()
		if len(self.positions):
			self.positions.write()
		self.positions = None

	def onOk(self, evt):
		x, y = self.xPos.GetValue(), self.yPos.GetValue()
		self.Destroy()
		wx.CallAfter(setMousePosition, x, y, announceMousePosition=True)

	def onCancel(self, evt):
		self.Destroy()


def disableInSecureMode(cls):
	return globalPluginHandler.GlobalPlugin if globalVars.appArgs.secure else cls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Cursor Movements")

	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		self.list_of_points = [] #["1000,1000", "1500,900", "2000,1100", "200,200"]
		self.current_idx = -1
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(cursorMovementsSettings)
		try:
			self.getShortCut()
		except Exception:
			pass

	def terminate(self):
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(CursorMovementsSettings)
		except IndexError:
			pass

	def event_gainFocus(self, obj, nextHandler):
		self.getShortCut()
		nextHandler()

	def getShortCut(self):
		appName = api.getFocusObject().appModule.appName
		if not os.path.exists(os.path.join(CMMousePositions, f"{appName}.gc")):
			self.clearGestureBindings()
			self.bindGestures(self.__gestures)
			return
		else:
			self.positions = ConfigObj(os.path.join(CMMousePositions, f"{appName}.gc"), encoding="UTF-8")
			for entry in self.positions.values():
				try:
					self.bindGesture(f"kb:{entry.split(',')[2]}", "click")
				except Exception:
					pass

	def script_click(self, gesture):
		for entry in self.positions.values():
			if entry.count(",") == 1:
				entry = entry + ",*"
			entry = entry.replace("CONTROL", "ctrl")
			try:
				if gesture.displayName == entry.split(",")[2]:
					x, y = entry.split(',')[:2]
					wx.CallAfter(setMousePosition, int(x), int(y), announceMousePosition=False, click=True)
					break
			except Exception:
				return

	@scriptHandler.script(
		# Translators: input help message for a Golden Cursor command.
		description=_("Opens a dialog listing mouse positions for the current application"),
		gesture="kb:nvda+control+l"
	)
	def script_mousePositionsList(self, gesture):
		# Don't even think about opening this dialog if positions list does not exist.
		appName = api.getFocusObject().appModule.appName
		if not os.path.exists(os.path.join(CMMousePositions, f"{appName}.gc")):
			# Translators: message presented when no mouse positions are available for the focused app.
			ui.message(_("No mouse positions for %s.") % appName)
		else:
			try:
				d = PositionsList(parent=gui.mainFrame, appName=appName)
				gui.mainFrame.prePopup()
				d.Raise()
				d.Show()
				gui.mainFrame.postPopup()
			except RuntimeError:
				pass

	@scriptHandler.script(
		# Translators: Input help message for a Golden Cursor command.
		description=_("Opens a dialog to label the current mouse position and saves it"),
		gesture="kb:nvda+shift+l"
	)
	def script_saveMousePosition(self, gesture):
		appName = "Current"
		x, y = winUser.getCursorPos()
		# Stringify coordinates early.
		x, y = str(x), str(y)
		d = EnterPositionName(
			# Translators: edit field label for new mouse position.
			gui.mainFrame, _("Enter the name for the current mouse position (x: {positionX}, Y: {positionY}").format(
				positionX=x, positionY=y
			),
			# Translators: title for save mouse position dialog.
			_("Save mouse position")
		)

		def callback(result):
			if result == wx.ID_OK:
				name = d.GetValue().rstrip()
				if name == "":
					return
				# appName = self.getMouse().appModule.appName
				# If the files path does not exist, create it now.
				if not os.path.exists(CMMousePositions):
					os.mkdir(CMMousePositions)
				position = ConfigObj(os.path.join(CMMousePositions, f"{appName}.gc"), encoding="UTF-8")
				position[name] = ",".join([x, y])
				entry = ",".join([x, y])
				list_of_points.add(entry)
				position.write()
				# Translators: presented when position (tag) has been saved.
				ui.message(_("Position saved in %s.") % position.filename)
		gui.runScriptModalDialog(d, callback)


	@scriptHandler.script(
		# Translators: Input help message for a Cursor Movements command.
		description=_("Reports current X and Y mouse position"),
		gesture="kb:nvda+windows+p"
	)
	def script_sayPosition(self, gesture):
		reportMousePosition()
		self.addMousePosition()

	def wind_mouse(obj, start_x, start_y, dest_x, dest_y, G_0=15, W_0=3, M_0=30, D_0=12, move_mouse=lambda x,y: None):
		'''
		WindMouse algorithm. Calls the move_mouse kwarg with each new step.
		Released under the terms of the GPLv3 license.
		G_0 - magnitude of the gravitational force
		W_0 - magnitude of the wind force fluctuations
		M_0 - maximum step size (velocity clip threshold)
		D_0 - distance where wind behavior changes from random to damped
		'''
		current_x,current_y = start_x,start_y
		v_x = v_y = W_x = W_y = 0
		dist = np.hypot(dest_x - start_x, dest_y - start_y)
		while dist >= 1:
			W_mag = min(W_0, dist)
			if dist >= D_0:
				W_x = W_x/sqrt3 + (2*random.random()-1)*W_mag/sqrt5
				W_y = W_y/sqrt3 + (2*random.random()-1)*W_mag/sqrt5
			else:
				W_x /= sqrt3
				W_y /= sqrt3
				if M_0 < 3:
					M_0 = random.random()*3 + 3
				else:
					M_0 /= sqrt5
			v_x += W_x + G_0*(dest_x-start_x)/dist
			v_y += W_y + G_0*(dest_y-start_y)/dist
			v_mag = np.hypot(v_x, v_y)
			if v_mag > M_0:
				v_clip = M_0/2 + random.random()*M_0/2
				v_x = (v_x/v_mag) * v_clip
				v_y = (v_y/v_mag) * v_clip
			start_x += v_x
			start_y += v_y
			# from the while statement
			dist = np.hypot(dest_x - start_x, dest_y - start_y)
			move_x = int(round(start_x))
			move_y = int(round(start_y))
			if current_x != move_x or current_y != move_y:
				#This should wait for the mouse polling interval
				#time.sleep(0.0001)
				setMousePosition(move_x,move_y)
				current_x =move_x
				current_y =move_y

		return current_x,current_y

	@scriptHandler.script(
		# Translators: Input help message for a Golden Cursor command.
		description=_("Moves the Mouse pointer to the right"),
		gesture="kb:nvda+windows+rightArrow"
	)
	def script_moveMouseRight(self, gesture):
		self.current_idx = self.current_idx + 1
		if self.current_idx >= len(self.list_of_points):
			self.current_idx = len(self.list_of_points) - 1
		self.gotoCursorPosition(self.current_idx)


	def addMousePosition(self, x=None, y=None):
		if x is None:
			cursorPos = winUser.getCursorPos()
			if x is None:
				x = cursorPos[0]
			if y is None:
				y = cursorPos[1]

		entry = ",".join([str(x), str(y)])
		self.list_of_points.append(entry)

	def gotoCursorPosition(self, idx):
		if self.current_idx < 0 or self.current_idx >= len(self.list_of_points):
			return
		x, y = winUser.getCursorPos()
		entry = self.list_of_points[idx]
		if entry.count(",") == 1:
			entry = entry + ",*"
			
		try:
			to_x, to_y = entry.split(',')[:2]
			wx.CallAfter(self.wind_mouse, x, y, int(to_x), int(to_y))
		except Exception:
			pass
		

	@scriptHandler.script(
		# Translators: Input help message for a Golden Cursor command.
		description=_("Moves the Mouse pointer to the left"),
		gesture="kb:nvda+windows+leftArrow"
	)
	def script_moveMouseLeft(self, gesture):
		self.current_idx = self.current_idx - 1
		if self.current_idx < 0:
			self.current_idx = 0
		self.gotoCursorPosition(self.current_idx)

	@scriptHandler.script(
		# Translators: Input help message for a Golden Cursor command.
		description=_("Moves the Mouse pointer down"),
		gesture="kb:nvda+windows+downArrow"
	)
	def script_moveMouseDown(self, gesture):
		self.current_idx = len(self.list_of_points) - 1
		self.gotoCursorPosition(self.current_idx)

	@scriptHandler.script(
		# Translators: Input help message for a Golden Cursor command.
		description=_("Moves the Mouse pointer up"),
		gesture="kb:nvda+windows+upArrow"
	)
	def script_moveMouseUp(self, gesture):
		self.current_idx = 0
		self.gotoCursorPosition(self.current_idx)


	def getMouse(self):
		return api.getDesktopObject().objectFromPoint(*winUser.getCursorPos())


# Add-on config database
# Borrowed from Enhanced Touch Gestures by Joseph Lee
confspec = {
	"reportNewMouseCoordinates": "boolean(default=true)",
	"mouseMovementUnit": "integer(min=1, max=100, default=5)",
}
config.conf.spec["goldenCursor"] = confspec


class cursorMovementsSettings(gui.settingsDialogs.SettingsPanel):
	# Translators: This is the label for the Golden Cursor settings category in NVDA Settings screen.
	title = _("Cursor Movements")

	def makeSettings(self, settingsSizer):
		gcHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.mouseCoordinatesCheckBox = gcHelper.addItem(
			# Translators: This is the label for a checkbox in the
			# Golden Cursor settings dialog.
			wx.CheckBox(self, label=_("&Announce new mouse coordinates when mouse moves"))
		)
		self.mouseCoordinatesCheckBox.SetValue(config.conf["goldenCursor"]["reportNewMouseCoordinates"])
		self.mouseMovementUnit = gcHelper.addLabeledControl(
			# Translators: The label for a setting in Golden Cursor settings dialog to change mouse movement units.
			_("Mouse movement &unit (in pixels)"), gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=1, max=100, initial=config.conf["goldenCursor"]["mouseMovementUnit"]
		)

	def onSave(self):
		config.conf["goldenCursor"]["reportNewMouseCoordinates"] = self.mouseCoordinatesCheckBox.IsChecked()
		config.conf["goldenCursor"]["mouseMovementUnit"] = self.mouseMovementUnit.Value
