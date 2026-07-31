# loyalty_service.py
from typing import Dict, Any, List, Optional
from odoo import models, api, _
from odoo.exceptions import ValidationError
from ..validators.loyalty_validator import LoyaltyValidator


class LoyaltyService(models.AbstractModel):
    _name = 'jabin.loyalty.service'
    _description = 'JABIN Loyalty Points Service'

    @api.model
    def get_settings(self, env=None) -> Dict[str, Any]:
        """Fetch system configuration parameters for loyalty points."""
        target_env = env or self.env
        icp = target_env['ir.config_parameter'].sudo()

        try:
            earning_rate = float(icp.get_param('jabin_loyalty.earning_rate', '1.0'))
        except (ValueError, TypeError):
            earning_rate = 1.0

        try:
            redemption_rate = float(icp.get_param('jabin_loyalty.redemption_rate', '100.0'))
        except (ValueError, TypeError):
            redemption_rate = 100.0

        try:
            min_redemption = int(icp.get_param('jabin_loyalty.min_redemption', '500'))
        except (ValueError, TypeError):
            min_redemption = 500

        return {
            'earning_rate': max(0.0001, earning_rate),
            'redemption_rate': max(0.0001, redemption_rate),
            'min_redemption': max(0, min_redemption)
        }

    @api.model
    def update_settings(self, env, earning_rate: float, redemption_rate: float, min_redemption: int):
        """Update system configuration parameters for loyalty points."""
        LoyaltyValidator.validate_settings(earning_rate, redemption_rate, min_redemption)
        icp = env['ir.config_parameter'].sudo()
        icp.set_param('jabin_loyalty.earning_rate', str(earning_rate))
        icp.set_param('jabin_loyalty.redemption_rate', str(redemption_rate))
        icp.set_param('jabin_loyalty.min_redemption', str(min_redemption))
        return True

    @api.model
    def calculate_earned_points(self, env, order_total: float) -> int:
        """
        Calculate loyalty points earned for an order total.
        Formula: Earned Points = int(Order Total * Earning Rate)
        """
        if order_total <= 0:
            return 0
        settings = self.get_settings(env)
        earned = int(order_total * settings['earning_rate'])
        return max(0, earned)

    @api.model
    def calculate_redemption_value(self, env, points: int) -> float:
        """
        Calculate SAR discount value for a given amount of loyalty points.
        Formula: Discount (SAR) = round(Points / Redemption Rate, 2)
        """
        if points <= 0:
            return 0.0
        settings = self.get_settings(env)
        discount = round(points / settings['redemption_rate'], 2)
        return max(0.0, discount)

    @api.model
    def validate_redemption(self, env, customer_id: int, points: int, order_total: float) -> bool:
        """Validate points redemption against customer balance and limits."""
        settings = self.get_settings(env)
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        LoyaltyValidator.validate_redemption(
            customer=customer,
            points=points,
            order_total=order_total,
            min_redemption=settings['min_redemption'],
            redemption_rate=settings['redemption_rate']
        )
        return True

    @api.model
    def deduct_redeemed_points(self, env, customer_id: int, points: int, order_id: Optional[int] = None):
        """Deduct redeemed points from customer wallet and create ledger transaction."""
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        order = env['jabin.order'].sudo().browse(order_id) if order_id else False
        order_total = order.total if order else 999999.0

        self.validate_redemption(env, customer_id, points, order_total)

        new_balance = customer.loyalty_points - points
        customer.sudo().write({
            'loyalty_points': new_balance,
            'total_redeemed_points': customer.total_redeemed_points + points
        })

        if order:
            order.sudo().write({'loyalty_points_deducted': True})

        order_name = order.name if order else ''
        desc = _("Redeemed %s points on Order %s") % (points, order_name) if order_name else _("Redeemed %s points") % points

        tx = env['jabin.loyalty.transaction'].sudo().create({
            'customer_id': customer.id,
            'order_id': order.id if order else False,
            'transaction_type': 'redeem',
            'points': -points,
            'balance_after': new_balance,
            'description': desc
        })

        if "jabin.notification.service" in env:
            try:
                env["jabin.notification.service"].send_loyalty_points(env, customer.id, points, 'redeem')
            except Exception:
                pass

        return tx

    @api.model
    def award_earned_points(self, env, order_id: int):
        """
        Award earned loyalty points to customer after order is successfully delivered.
        """
        order = env['jabin.order'].sudo().browse(order_id)
        if not order.exists():
            return False

        if order.loyalty_points_awarded:
            return False

        if order.state != 'delivered':
            return False

        earned_points = self.calculate_earned_points(env, order.total)
        if earned_points <= 0:
            order.sudo().write({'loyalty_points_earned': 0, 'loyalty_points_awarded': True})
            return False

        customer = order.customer_id
        new_balance = customer.loyalty_points + earned_points
        customer.sudo().write({
            'loyalty_points': new_balance,
            'total_earned_points': customer.total_earned_points + earned_points
        })

        order.sudo().write({
            'loyalty_points_earned': earned_points,
            'loyalty_points_awarded': True
        })

        tx = env['jabin.loyalty.transaction'].sudo().create({
            'customer_id': customer.id,
            'order_id': order.id,
            'transaction_type': 'earn',
            'points': earned_points,
            'balance_after': new_balance,
            'description': _("Earned %s points from completed Order %s") % (earned_points, order.name)
        })

        if "jabin.notification.service" in env:
            try:
                env["jabin.notification.service"].send_loyalty_points(env, customer.id, earned_points, 'earn')
            except Exception:
                pass

        return tx


    @api.model
    def reverse_order_points(self, env, order_id: int):
        """
        Reverse awarded points and/or restore redeemed points if an order is cancelled or refunded.
        """
        order = env['jabin.order'].sudo().browse(order_id)
        if not order.exists():
            return False

        customer = order.customer_id

        # 1. Reverse awarded earned points
        if order.loyalty_points_awarded and order.loyalty_points_earned > 0:
            earned = order.loyalty_points_earned
            new_balance = max(0, customer.loyalty_points - earned)
            customer.sudo().write({
                'loyalty_points': new_balance,
                'total_earned_points': max(0, customer.total_earned_points - earned)
            })
            order.sudo().write({'loyalty_points_awarded': False})
            env['jabin.loyalty.transaction'].sudo().create({
                'customer_id': customer.id,
                'order_id': order.id,
                'transaction_type': 'refund_adjustment',
                'points': -earned,
                'balance_after': new_balance,
                'description': _("Reversed %s earned points for cancelled/refunded Order %s") % (earned, order.name)
            })

        # 2. Restore redeemed points
        if order.loyalty_points_deducted and order.points_redeemed > 0:
            redeemed = order.points_redeemed
            new_balance = customer.loyalty_points + redeemed
            customer.sudo().write({
                'loyalty_points': new_balance,
                'total_redeemed_points': max(0, customer.total_redeemed_points - redeemed)
            })
            order.sudo().write({'loyalty_points_deducted': False})
            env['jabin.loyalty.transaction'].sudo().create({
                'customer_id': customer.id,
                'order_id': order.id,
                'transaction_type': 'refund_adjustment',
                'points': redeemed,
                'balance_after': new_balance,
                'description': _("Restored %s redeemed points for cancelled/refunded Order %s") % (redeemed, order.name)
            })

        return True

    @api.model
    def manual_adjust_points(self, env, customer_id: int, points_change: int, reason: str, admin_user_id: Optional[int] = None):
        """Admin capability to manually add or deduct customer loyalty points."""
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        LoyaltyValidator.validate_manual_adjustment(customer, points_change, reason)

        new_balance = customer.loyalty_points + points_change
        vals = {'loyalty_points': new_balance}
        if points_change > 0:
            vals['total_earned_points'] = customer.total_earned_points + points_change
        elif points_change < 0:
            vals['total_redeemed_points'] = customer.total_redeemed_points + abs(points_change)

        customer.sudo().write(vals)

        tx = env['jabin.loyalty.transaction'].sudo().create({
            'customer_id': customer.id,
            'transaction_type': 'manual_adjustment',
            'points': points_change,
            'balance_after': new_balance,
            'description': reason,
            'created_by_id': admin_user_id or env.user.id
        })
        return tx

    @api.model
    def get_customer_loyalty_summary(self, env, customer_id: int) -> Dict[str, Any]:
        """Get summary of customer loyalty wallet balance, history, and rates."""
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        settings = self.get_settings(env)
        max_discount_sar = round(customer.loyalty_points / settings['redemption_rate'], 2) if customer.loyalty_points >= settings['min_redemption'] else 0.0

        return {
            'customer_id': customer.id,
            'customer_name': customer.name,
            'loyalty_points': customer.loyalty_points,
            'total_earned_points': customer.total_earned_points,
            'total_redeemed_points': customer.total_redeemed_points,
            'earning_rate': settings['earning_rate'],
            'redemption_rate': settings['redemption_rate'],
            'min_redemption': settings['min_redemption'],
            'is_eligible_for_redemption': customer.loyalty_points >= settings['min_redemption'],
            'max_redeemable_discount_sar': max_discount_sar
        }

    @api.model
    def get_customer_transaction_history(self, env, customer_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get transaction ledger history for customer."""
        customer = env['res.users'].sudo().browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer not found."))

        txs = env['jabin.loyalty.transaction'].sudo().search(
            [('customer_id', '=', customer.id)],
            order='date desc, id desc',
            limit=limit,
            offset=offset
        )
        res = []
        for tx in txs:
            res.append({
                'id': tx.id,
                'date': fields.Datetime.to_string(tx.date),
                'transaction_type': tx.transaction_type,
                'transaction_type_label': dict(tx._fields['transaction_type'].selection).get(tx.transaction_type),
                'points': tx.points,
                'balance_after': tx.balance_after,
                'description': tx.description,
                'order_id': tx.order_id.id if tx.order_id else None,
                'order_name': tx.order_id.name if tx.order_id else None,
            })
        return res
