import torch
import torch.nn as nn

class AsymmetricLoss(nn.Module):
    def __init__(self, gamma_neg=4, gamma_pos=1, clip=0.05, eps=1e-8, disable_torch_grad_focal_loss=True):
        super(AsymmetricLoss, self).__init__()

        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip = clip
        self.disable_torch_grad_focal_loss = disable_torch_grad_focal_loss
        self.eps = eps

    def forward(self, x, y):
        """"
        Parameters
        ----------
        x: input logits
        y: targets (multi-label binarized vector)
        """

        # Calculating Probabilities
        x_sigmoid = torch.sigmoid(x)
        xs_pos = x_sigmoid
        xs_neg = 1 - x_sigmoid

        # Asymmetric Clipping
        if self.clip is not None and self.clip > 0:
            xs_neg = (xs_neg + self.clip).clamp(max=1)

        # Basic CE calculation
        los_pos = y * torch.log(xs_pos.clamp(min=self.eps))
        los_neg = (1 - y) * torch.log(xs_neg.clamp(min=self.eps))
        loss = los_pos + los_neg

        # Asymmetric Focusing
        if self.gamma_neg > 0 or self.gamma_pos > 0:
            if self.disable_torch_grad_focal_loss:
                torch.set_grad_enabled(False)
            pt0 = xs_pos * y
            pt1 = xs_neg * (1 - y)  # pt = p if t > 0 else 1-p
            pt = pt0 + pt1
            one_sided_gamma = self.gamma_pos * y + self.gamma_neg * (1 - y)
            one_sided_w = torch.pow(1 - pt, one_sided_gamma)
            if self.disable_torch_grad_focal_loss:
                torch.set_grad_enabled(True)
            loss *= one_sided_w

        return -loss.sum()

class MultiLabelSoftmax(nn.Module):
    def __init__(self, gamma_pos=1., gamma_neg=1.):
        super(MultiLabelSoftmax, self).__init__()
        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg

    def forward(self, outputs, targets):
        targets = targets.float()
        outputs = (1 - 2 * targets) * outputs
        y_pred_neg = outputs - targets * 1e15
        y_pred_pos = outputs - (1 - targets) * 1e15
        zeros = torch.zeros_like(outputs[..., :1])
        y_pred_neg = torch.cat([y_pred_neg, zeros], dim=-1)
        y_pred_pos = torch.cat([y_pred_pos, zeros], dim=-1)

        neg_loss = (1 / self.gamma_neg) * torch.log(torch.sum(torch.exp(self.gamma_neg * y_pred_neg), dim=-1))
        pos_loss = (1 / self.gamma_pos) * torch.log(torch.sum(torch.exp(self.gamma_pos * y_pred_pos), dim=-1))

        loss = torch.mean(neg_loss + pos_loss)
        return loss


def create_loss(loss_fc):
    if loss_fc=='mlsm':    
        criterion = nn.MultiLabelSoftMarginLoss(reduction='sum')
    elif loss_fc == 'bce':
        criterion = nn.BCEWithLogitsLoss(reduction='sum') 
    elif loss_fc == 'focal':
        criterion = AsymmetricLoss(gamma_neg=1, gamma_pos=1, clip=0, disable_torch_grad_focal_loss=True)
    elif loss_fc == 'asl':
        criterion = AsymmetricLoss(gamma_neg=4, gamma_pos=0, clip=0.05, disable_torch_grad_focal_loss=True)
    elif loss_fc == 'halfasl':
        criterion = AsymmetricLoss(gamma_neg=1, gamma_pos=0, clip=0, disable_torch_grad_focal_loss=True)
    elif loss_fc == 'mlsoft':
        criterion = MultiLabelSoftmax( gamma_pos=1, gamma_neg=1)   
    else:
        raise ValueError('loss not implemented')

    return criterion

