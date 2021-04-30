# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

import klibs
from klibs import P
from klibs.KLGraphics import *
from klibs.KLUtilities import *
from klibs.KLUserInterface import *
from klibs.KLGraphics.KLNumpySurface import *
from CompTrack import *

import subprocess


class CompensatoryTrackingTask(klibs.Experiment):
	comp_track = None

	def setup(self):

		# PVTarget's mouse velocity algo triggers OS X's Settings->Accessibility->Display->Shake Mouse Pointer To Locate
		if not P.development_mode:
			self.check_osx_mouse_shake_setting()

		self.txtm.add_style('UserAlert', 16, (255, 000, 000))

		self.comp_track = CompTrack()


		self.comp_track.task_params['exp_duration'] = 150  # seconds
		self.comp_track.task_params['poll_while_moving'] = True
		self.comp_track.task_params['reset_target_after_poll'] = True  # sets target back to fixation after a response

		self.comp_track.generate_PVT_timestamps()

		clear()
		flip()
		mouse_pos(False, P.screen_c)
		hide_mouse_cursor()
		session_start = now()
		while (now() - session_start) < self.comp_track.task_params['exp_duration']:
			events = pump(True)
			self.comp_track.refresh(events)
			ui_request(queue=events)

		# self.db.export(table='comp_track_data')
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
