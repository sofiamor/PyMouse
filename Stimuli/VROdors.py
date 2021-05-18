from Stimulus import *


class VROdors(Stimulus):
    def get_cond_tables(self):
        return ['VRCond']

    def prepare(self):
        self._get_new_cond()

    def init(self, period=None):
        self.beh.start_odor(0)
        self.logger.log('StimOnset', dict(period=period))
        self.isrunning = True
        self.timer.start()

    def loc2odor(self, x, y):
        xmx = self.curr_cond['x_max']
        ymx = self.curr_cond['y_max']
        fun = self.curr_cond['fun']
        a = (np.abs(np.array([0, 0, xmx, xmx]) - x) / xmx) ** 2
        b = (np.abs(np.array([0, ymx, ymx, 0]) - y) / ymx) ** 2
        return (1 - ((a + b) / 2) ** .5) ** fun * 100

    def present(self):
        x, y = self.beh.get_position()
        odor_dutycycle = self.loc2odor(x, y)
        self.beh.update_odor(odor_dutycycle[self.curr_cond['delivery_port']-1])
        print(x, y)

    def stop(self):
        self.isrunning = False
