import itertools
import math
import numpy as np
import pytest
from trend_scope.models.text_events.kleinberg import kleinberg
from trend_scope.models.serialization import dumps


def test_kleinberg_exact_short_path_objective():
    t=np.array([0.,3.,3.1,3.2,6.])
    result=kleinberg(t,rate_multiplier=2,gamma=.3)
    rates=result['state_rates']; gaps=np.diff(t)
    def cost(path):
        transitions=sum(max(0,b-a) for a,b in zip((0,)+path[:-1],path))
        return sum(rates[k]*gap-math.log(rates[k]) for k,gap in zip(path,gaps))+.3*math.log(4)*transitions
    best=min(cost(path) for path in itertools.product(range(len(rates)),repeat=4))
    assert result['objective']==pytest.approx(best)
    assert cost(tuple(result['gap_states']))==pytest.approx(best)
    dumps(result)


def test_kleinberg_constant_and_invalid_arrivals():
    np.testing.assert_array_equal(kleinberg(np.arange(8))['gap_states'],0)
    with pytest.raises(ValueError):
        kleinberg([0,1,1])
