from sklearn.preprocessing import MultiLabelBinarizer

from tagc.io_utils import (
    build_eval_json,
    dump_json,
    dump_state,
    load_datazip,
    load_json,
)
from tagc.model import StandaloneModel, label_output
from tagc.validation import dimension_reduction, get_unlabelled_state
from tagc.visualization import state_plot


def form_eval(
    model,
    mlb,
    unlabelled_p="outputsK/unlabelled.json",
    outdir="outputs",
    over=5,
    marker="",
    skip_state=False,
):
    sampled_cases = load_json(unlabelled_p)
    if not skip_state:
        sampled_state = get_unlabelled_state(model, sampled_cases, mlb)
        dump_state(sampled_state, state_p=f"{outdir}/unstate{marker}.pkl")
        unstate_df = dimension_reduction(sampled_state, "TSNE", n_components=2)
        unstate_df.to_csv(f"{outdir}/unlabel_tsne{marker}.csv")
        fig = state_plot(unstate_df, 12)
        fig.write_image(f"{outdir}/unlabelled_TSNE{marker}.pdf")
        fig.write_html(f"{outdir}/unlabel_tsne{marker}.html")
    preds = model.over_predict(sampled_cases, n=over)
    thresh_items = label_output(preds)
    pred_prob = [list(zip(mlb.classes_, pred)) for pred in preds]
    eval_json = build_eval_json(sampled_cases, pred_prob, thresh_items)
    dump_json(f"{outdir}/eval{marker}.json", eval_json)


if __name__ == "__main__":
    ds = load_datazip("dataset.zip")
    mlb = MultiLabelBinarizer().fit(ds.y_tags)
    model_p = "lab4/keepKey_200/model"
    model = StandaloneModel.from_path(model_p, keep_key=True, max_len=150)
    form_eval(model, mlb)
