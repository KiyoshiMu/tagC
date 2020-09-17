import re
from collections import Counter, defaultdict
from typing import DefaultDict, List

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.preprocessing import MultiLabelBinarizer

from .domain import Case, Mask, MaskedParent, MaskRet, Trace
from .model import StandaloneModel


class MaskMaker:
    def __init__(self, pattern=r"\w+"):
        self.finder = re.compile(pattern)

    def __call__(self, case: Case):
        masks = []
        for field, sent in case.items():
            for match in self.finder.finditer(sent):
                start, end = match.span()
                mask = Mask(field, start, end)
                masks.append(mask)
        masked_parent = MaskedParent(masks, case)
        return masked_parent


class MaskExplainer:
    def __init__(self, mlb: MultiLabelBinarizer, mask_maker: MaskMaker = None):
        if mask_maker is None:
            self.mask_maker = MaskMaker()
        else:
            self.mask_maker = mask_maker
        self.mlb = mlb

    def explain(self, model: StandaloneModel, case: Case):
        origin_output = model.predict([case])
        masked_parent = self.mask_maker(case)
        masked_cases = masked_parent.masked_cases()
        masked_outputs = model.predict(masked_cases)

        mask_words = np.array(masked_parent.mask_words())

        trace = Trace(origin_output, masked_outputs, mask_words)
        ret = self.analysis_trace(trace)
        return ret

    def analysis_trace(self, trace: Trace):
        def sort_col_descend(values, col):
            return np.argsort(values[:, col])[::-1]

        pred = trace.origin_output >= 0.5
        bool_idx = pred[0]
        trace.important_change = (
            trace.origin_output[:, bool_idx] - trace.masked_outputs[:, bool_idx]
        )
        pred_tag = self.mlb.inverse_transform(pred)[0]
        rets = []
        for idx, tag in enumerate(pred_tag):
            rank = sort_col_descend(trace.important_change, idx)
            importance = [
                (word, value)
                for word, value in zip(
                    trace.mask_words[rank], trace.important_change[:, idx][rank]
                )
            ]
            rets.append(MaskRet(tag, importance))
        self.trace = trace
        return rets

    def show_trace(self):
        trace = self.trace
        return trace.origin_output, trace.masked_outputs, trace.important_change


def plot_explanation(rets: List[MaskRet], dash=False):
    fig = make_subplots(
        rows=len(rets), cols=1, subplot_titles=tuple(ret.tag for ret in rets)
    )
    for loc, mask_ret in enumerate(rets, start=1):
        importance = mask_ret.importance
        words_p = [p[0] for p in importance if p[1] >= 0]
        values_p = [p[1] for p in importance if p[1] >= 0]
        words_n = [p[0] for p in importance if p[1] < 0]
        values_n = [p[1] for p in importance if p[1] < 0]

        fig.add_trace(go.Bar(x=words_p, y=values_p, name="pos"), row=loc, col=1)
        fig.add_trace(go.Bar(x=words_n, y=values_n, name="neg"), row=loc, col=1)
        # fig.update_xaxes(title_text="word", row=loc, col=1)
        fig.update_yaxes(title_text="influence", row=loc, col=1)
    fig.layout.update(showlegend=False)
    if dash:
        return fig
    fig.show()


# TODO
def top_keywords(
    mask_explainer: MaskExplainer, model: StandaloneModel, cases: List[Case], top_n=5
):
    rets = collect_rets(mask_explainer, model, cases)
    return sum_keywords(rets, top_n)


# Top 5 keywords for each tags
def collect_rets(
    mask_explainer: MaskExplainer, model: StandaloneModel, cases: List[Case]
):
    rets = []
    for case in cases:
        rets.extend(mask_explainer.explain(model, case))
    return rets


def sum_keywords(rets: List[MaskRet], top_n=5):
    dashboard: DefaultDict[str, Counter] = defaultdict(Counter)

    for ret in rets:
        dashboard[ret.tag].update(ret.importance[:top_n])
    return dashboard
