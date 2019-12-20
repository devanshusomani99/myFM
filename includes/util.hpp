#ifndef MYFM_UTIL_HPP
#define MYFM_UTIL_HPP

#include <random>
#include <sstream>

namespace myFM { 
    using namespace std;

/*
Sample from truncated normal distribution.
https://arxiv.org/pdf/0907.4010.pdf
Proposition 2.3.
*/
template <typename Real>
inline Real sample_truncated_normal_left(mt19937 &gen, Real mu_minus) {
  if (mu_minus < 0) {
    normal_distribution<Real> dist(0, 1);
    while (true) {
      Real z = dist(gen); 
      if (z > mu_minus){
        return z;
      }
    }
  } else {
    Real alpha_star = ( mu_minus + std::sqrt( mu_minus * mu_minus + 4 ) ) / 2;
    uniform_real_distribution<Real> dist(0, 1); 
    while (true) {
       Real z = - std::log(dist(gen)) / alpha_star + mu_minus;
       Real rho = std::exp( - ( z -alpha_star ) * (z -alpha_star) / 2);
       Real u = dist(gen);
       if (u < rho) {
         return z;
       }
    }
  }
}

template <typename Real>
inline Real sample_truncated_normal_left(mt19937 &gen, Real mean, Real std, Real mu_minus) {
  return mean + std * sample_truncated_normal_left(gen, (mu_minus -mean) / std );
}

template <typename Real> 
inline Real sample_truncated_normal_right(mt19937 &gen, Real mu_plus) { 
  return - sample_truncated_normal_left(gen, -mu_plus);
}

template <typename Real>
inline Real sample_truncated_normal_right(mt19937 &gen, Real mean, Real std, Real mu_plus) {
  return mean + std * sample_truncated_normal_right(gen, (mu_plus - mean) / std );
}

struct StringBuilder  {
  inline StringBuilder(): oss_() {} 

  template<typename T>
  inline StringBuilder & add(const T & arg) {
    oss_ << arg;
    return *this;
  } 

  template<typename T>
  inline StringBuilder & operator()(const T & arg) {
    oss_ << arg;
    return *this;
  } 

  template<typename T>
  inline StringBuilder & space_and_add(const T & arg) {
    oss_ << " " << arg;
    return *this;
  } 

  template<typename T, typename F>
  inline StringBuilder & add(const T & arg, const T & fmt) {
    oss_ << fmt << arg;
    return *this;
  }

  inline string build () { return oss_.str();}

  private:
  ostringstream oss_;
};

} // namespace myFM

#endif
