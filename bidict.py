
class BiDict:
    def __init__(self, a, ka_f, b, kb_f):
        self.a_b = {}
        self.b_a = {}
        self.ka_f, self.kb_f = ka_f, kb_f
        def a_b(k):
            return self.a_b.get(self.get_ka(k))
        def b_a(k):
            return self.b_a.get(self.get_kb(k))
        def a_values():
            return self.a_b.values()
        def b_values():
            return self.b_a.values()

        setattr(self, "%s_to_%s" % (a, b), a_b)
        setattr(self, "%s_to_%s" % (b, a), b_a)
        setattr(self, "%s_values" % (a), a_values)
        setattr(self, "%s_values" % (b), b_values)

    def get_ka(self, a):
        if self.ka_f is None:
            return a
        else:
            return self.ka_f(a)

    def get_kb(self, b):
        if self.kb_f is None:
            return b
        else:
            return self.kb_f(b)

    def set(self, a, b):
        ka = self.get_ka(a)
        if ka in self.a_b:
            dup = self.get_kb(self.a_b[ka])
            del self.b_a[dup]
        kb = self.get_kb(b)
        if kb in self.b_a:
            dup = self.get_ka(self.b_a[kb])
            del self.a_b[dup]
        self.a_b[ka] = b
        self.b_a[kb] = a

    def __len__(self):
        if len(self.a_b) != len(self.b_a):
            print("mismatch of internal length: %d vs. %d" % (len(self.a_b), len(self.b_a)), file=sys.stderr)
        return len(self.a_b)

