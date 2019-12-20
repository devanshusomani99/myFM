#ifndef MYFM_FM_HPP
#define MYFM_FM_HPP
#include "definitions.hpp"
#include <cmath>

namespace myFM {

using namespace std;

template <typename Real> struct FM {

  using DenseMatrix = Eigen::Matrix<Real, -1, -1, Eigen::ColMajor>;

  using Vector = Eigen::Matrix<Real, -1, 1>;

  using SparseMatrix = Eigen::SparseMatrix<Real, Eigen::RowMajor>;

  using SparseVector = Eigen::SparseVector<Real>;

  inline FM(int n_factors, size_t n_groups)
      : n_factors(n_factors), initialized(false) {}
  inline FM(int n_factors) : FM(n_factors, 1) {}

  inline FM(const FM &other)
      : n_factors(other.n_factors), V(other.V), w(other.w), w0(other.w0), initialized(other.initialized) {}

  inline void initialize_weight(int n_features, Real init_std, mt19937 &gen) {
    initialized = false;
    auto get_rand = [&gen, init_std, this](Real dummy) {
      return this->nd(gen) * init_std;
    };
    V = DenseMatrix{n_features, n_factors}.unaryExpr(get_rand);
    w = Vector{n_features}.unaryExpr(get_rand);
    w0 = get_rand(1);
    initialized = true;
  }

  inline Vector add_q(const SparseMatrix &X, Eigen::Ref<Vector> q) {
    q += X * V;
  }

  inline Vector predict_score(const SparseMatrix &X) const {
    if (!initialized) {
      throw std::runtime_error("get_score called before initialization");
    }
    // Vector result = Vector::Constant(X.rows(), w0_);
    Vector result = w0 + (X * w).array();
    result.array() += (X * V).array().square().rowwise().sum() * 0.5;
    result -=
        (X.cwiseAbs2()) * ((0.5 * V.array().square().rowwise().sum()).matrix());

    return result;
  }

  const int n_factors;
  DenseMatrix V; // (n_feature, n_factor) - matrix
  Vector w;
  Real w0;
  normal_distribution<Real> nd;

private:
  bool initialized;
};

} // namespace myFM
#endif
