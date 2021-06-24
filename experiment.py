# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

import klibs
from klibs import P
from klibs.KLGraphics import *
from klibs.KLUtilities import *
#from klibs.KLUserInterface import *
from klibs.KLGraphics.KLNumpySurface import *
from CompTrack import *

import subprocess


class CompensatoryTrackingTask(klibs.Experiment):
	comp_track = None

	def setup(self):

		# Ensure mouse-shake setting is disabled, as it will be triggered by mouse input
		if not P.development_mode:
			self.txtm.add_style('UserAlert', 16, (255, 000, 000))
			self.check_osx_mouse_shake_setting()

		# CompTrack class handles all events
		self.comp_track = CompTrack()

		# Set session parameters
		self.comp_track.session_params['exp_duration'] = 300  # Total duration of session, in seconds
		self.comp_track.session_params['reset_target_after_poll'] = True  # Should cursor reset to center after PVT events?

		# Compute timestamps to present PVT at
		self.comp_track.generate_PVT_timestamps()

		# Ensure display has been wiped before starting
		clear()
		flip()

		# Ensure mouse starts at centre and set invisible
		mouse_pos(False, P.screen_c)
		hide_mouse_cursor()

		# Begin testing session
		session_start = now()
		while (now() - session_start) < self.comp_track.session_params['exp_duration']:
			events = pump(True)  # Check for input
			self.comp_track.refresh(events)  # Process inputs, if any, and update task state
			ui_request(queue=events)  # Check input for quit command

		# self.db.export(table='comp_track_data')

		# Exit program
		exit()

	def block(self):
		pass

	def setup_response_collector(self):
		pass

	def trial_prep(self):
		pass

	def trial(self):

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number
		}

	def trial_clean_up(self):
		pass

	def clean_up(self):
		pass


	def check_osx_mouse_shake_setting(self):
		p = subprocess.Popen(
			"defaults read ~/Library/Preferences/.GlobalPreferences CGDisableCursorLocationMagnification 1", shell=True)
		if p is 0:
			fill((025, 025, 28))
			blit(NumpySurface(import_image_file('ExpAssets/Resources/image/accessibility_warning.png')), 5, P.screen_c)
			msg = 'Please ensure cursor shake-magnification is off before running this experiment.'
			x_pos = int((P.screen_y - 568) * 0.25) + 16
			message(msg, 'UserAlert', [P.screen_c[0], x_pos], 5)
			flip()
			any_key()
			quit()
