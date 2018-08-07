import json

from visidata import *


def open_json(p):
    return JSONSheet(p.name, source=p, jsonlines=False)

def open_jsonl(p):
    return JSONSheet(p.name, source=p, jsonlines=True)


class JSONSheet(PythonSheet):
    @asyncthread
    def reload(self):
        self.colnames = {}  # [colname] -> Column
        self.columns.clear()

        if not self.jsonlines:
            try:
                self.reload_json()
            except ValueError as e:
                status('trying jsonl')
                self.jsonlines = True

        if self.jsonlines:
            self.reload_jsonl()

    def reload_json(self):
        self.rows = []
        with self.source.open_text() as fp:
            ret = json.load(fp)

        if isinstance(ret, dict):
            self.rows = [ret]
            self.columns = []
            for k in self.rows[0]:
                self.addColumn(ColumnItem(k, type=deduceType(self.rows[0][k])))
        else:
            self.rows = []
            for row in Progress(ret):
                self.addRow(row)

    def reload_jsonl(self):
        with self.source.open_text() as fp:
            self.rows = []
            for L in fp:
                try:
                    self.addRow(json.loads(L))
                except Exception as e:
                    e.stacktrace = stacktrace()
                    self.addRow(TypedExceptionWrapper(json.loads, L, exception=e))

    def addRow(self, row, index=None):
        super().addRow(row, index=index)
        if isinstance(row, dict):
            for k in row:
                if k not in self.colnames:
                    c = ColumnItem(k, type=deduceType(row[k]))
                    self.colnames[k] = c
                    self.addColumn(c)
            return row

    def newRow(self):
        return {}


## saving json and jsonl

class vjsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, TypedExceptionWrapper):
            if options.error_is_null:
                return None
            return {type(o.exception).__name__: str(o.exception), 'value': str(o.val)}
        elif isinstance(o, TypedWrapper):
            return o.val
        return json.JSONEncoder.default(self, o)


def _rowdict(cols, row):
    return {c.name: wrapply(c.getTypedValue, row) for c in cols}


@asyncthread
def save_json(p, vs):
    with p.open_text(mode='w') as fp:
        vcols = vs.visibleCols
        for chunk in vjsonEncoder().iterencode([_rowdict(vcols, r) for r in Progress(vs.rows)]):
            fp.write(chunk)


@asyncthread
def save_jsonl(p, vs):
    with p.open_text(mode='w') as fp:
        vcols = vs.visibleCols
        jsonenc = vjsonEncoder()
        for r in Progress(vs.rows):
            rowdict = _rowdict(vcols, r)
            fp.write(jsonenc.encode(rowdict) + '\n')
