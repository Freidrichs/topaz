class TestComparable(object):
    def test_less(self, ec):
        w_res = ec.space.execute(ec, "return 'a' < 'b'")
        assert w_res is ec.space.w_true

    def test_greater(self, ec):
        w_res = ec.space.execute(ec, "return 'a' > 'b'")
        assert w_res is ec.space.w_false
